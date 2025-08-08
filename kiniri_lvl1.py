import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, ttk
from PIL import Image, ImageTk
import os
import shutil
import sys
import io
import xml.etree.ElementTree as ET
from shutil import copyfile

# Set console output encoding to UTF-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

SAVE_FOLDER = "level_data"
BLOCK_SIZE = 64
# Canvas size
CANVAS_WIDTH = 1800
CANVAS_HEIGHT = 1200


def snap_to_grid(x, y):
    """Привязка к сетке"""
    x = max(BLOCK_SIZE // 2, min(CANVAS_WIDTH - BLOCK_SIZE // 2, x))
    y = max(BLOCK_SIZE // 2, min(CANVAS_HEIGHT - BLOCK_SIZE // 2, y))
    snapped_x = (x // BLOCK_SIZE) * BLOCK_SIZE + BLOCK_SIZE // 2
    snapped_y = (y // BLOCK_SIZE) * BLOCK_SIZE + BLOCK_SIZE // 2
    return snapped_x, snapped_y


class LevelEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Редактор Уровня")
        self.root.geometry(f"{CANVAS_WIDTH+20}x{CANVAS_HEIGHT+150}")

        # Create the canvas with a larger virtual size for panning
        self.canvas_width = CANVAS_WIDTH * 2  # Double the size for panning
        self.canvas_height = CANVAS_HEIGHT * 2
        self.view_x = 0
        self.view_y = 0
        
        # Create a frame for the canvas and scrollbars
        self.canvas_frame = tk.Frame(root)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollbars
        self.h_scrollbar = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.v_scrollbar = tk.Scrollbar(self.canvas_frame)
        
        # Create the canvas with scrollable area
        self.canvas = tk.Canvas(
            self.canvas_frame,
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            bg="gray",
            xscrollcommand=self.h_scrollbar.set,
            yscrollcommand=self.v_scrollbar.set,
            scrollregion=(0, 0, self.canvas_width, self.canvas_height)
        )
        
        # Configure scrollbars
        self.h_scrollbar.config(command=self.canvas.xview)
        self.v_scrollbar.config(command=self.canvas.yview)
        
        # Grid layout
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Configure grid weights
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        
        # Bind mouse wheel for zooming
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)

        # Create frame for buttons
        self.frame = tk.Frame(root)
        self.frame.pack(fill=tk.X, pady=5)
        
        # Recent blocks frame
        self.recent_frame = tk.Frame(root, height=30, bg='#f0f0f0')
        self.recent_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Label for recent blocks
        tk.Label(self.recent_frame, text="Недавние блоки:", bg='#f0f0f0').pack(side=tk.LEFT, padx=5)
        
        # Frame for recent block buttons
        self.recent_buttons_frame = tk.Frame(self.recent_frame, bg='#f0f0f0')
        self.recent_buttons_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # List to store recent blocks (max 5)
        self.recent_blocks = []
        self.max_recent_blocks = 5

        # Buttons frame
        button_frame = tk.Frame(self.frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        # Image buttons
        tk.Button(button_frame, text="Фон", command=self.load_background, width=8).pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="Блок", command=self.load_block, width=8).pack(side=tk.LEFT, padx=2)
        
        # Separator
        ttk.Separator(button_frame, orient='vertical').pack(side=tk.LEFT, fill='y', padx=5)
        
        # Level operations
        tk.Button(button_frame, text="Открыть", command=self.load_level, width=8).pack(side=tk.LEFT, padx=2)
        tk.Button(button_frame, text="Сохранить", command=self.save_level, width=8).pack(side=tk.LEFT, padx=2)
        
        # Recent blocks dropdown
        self.recent_btn = tk.Menubutton(button_frame, text="Недавние ▼", width=12)
        self.recent_btn.pack(side=tk.LEFT, padx=2)
        self.recent_menu = tk.Menu(self.recent_btn, tearoff=0)
        self.recent_btn.config(menu=self.recent_menu)

        self.blocks = {}              # имя блока -> {path, img, tk_img}
        self.current_block = None
        self.bg_image = None
        self.bg_path = None
        self.objects = []             # список всех объектов на карте
        self.image_references = []    # список для хранения ссылок на PhotoImage

        self.drag_data = {
            "item": None,
            "index": None,
            "start_x": 0,
            "start_y": 0
        }
        
        # Track selected block
        self.selected_block = None

        self.canvas.bind("<Button-3>", self.place_or_delete_block)  # ПКМ — создать или удалить
        self.canvas.bind("<Button-2>", self.copy_block)             # СКМ — копировать блок
        self.canvas.bind("<Button-1>", self.pan_canvas)             # ЛКМ — панорамирование
        self.canvas.bind("<B1-Motion>", self.pan_canvas)            # ЛКМ движение — панорамирование
        self.canvas.bind("<ButtonRelease-1>", lambda e: None)       # Пустой обработчик для отпускания ЛКМ
        
        # Bind arrow keys for navigation
        self.root.bind("<Left>", lambda e: self.pan_view(-50, 0))
        self.root.bind("<Right>", lambda e: self.pan_view(50, 0))
        self.root.bind("<Up>", lambda e: self.pan_view(0, -50))
        self.root.bind("<Down>", lambda e: self.pan_view(0, 50))
        
        # Initialize panning state
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.is_panning = False
        

        os.makedirs(SAVE_FOLDER, exist_ok=True)

    def load_background(self):
        path = filedialog.askopenfilename(filetypes=[
            ("Image Files", "*.png;*.jpg;*.jpeg"),
            ("Tiled Map Files", "*.tmx")
        ])
        if not path:
            return
            
        if path.lower().endswith('.tmx'):
            self.load_tmx_file(path)
            return
        if path:
            self.bg_path = path
            # Load and tile the background image
            try:
                original_img = Image.open(path)
                img_width, img_height = original_img.size
                
                # Create a new image large enough to hold 40 tiles (5x8 grid)
                tiled_img = Image.new('RGBA', (img_width * 8, img_height * 5))
                
                # Tile the image
                for x in range(0, img_width * 8, img_width):
                    for y in range(0, img_height * 5, img_height):
                        tiled_img.paste(original_img, (x, y))
                
                # Resize to fit canvas while maintaining aspect ratio
                tiled_img = tiled_img.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)
                
                self.bg_image = ImageTk.PhotoImage(tiled_img)
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self.bg_image)
                
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить изображение: {str(e)}")
    
    def load_tmx_file(self, tmx_path):
        """Загружает карту из файла .tmx"""
        try:
            # Парсим XML файл
            tree = ET.parse(tmx_path)
            root = tree.getroot()
            
            # Получаем размеры карты
            map_width = int(root.get('width'))
            map_height = int(root.get('height'))
            tile_width = int(root.get('tilewidth'))
            tile_height = int(root.get('tileheight'))
            
            # Ищем слой с данными тайлов
            for layer in root.findall('layer'):
                data = layer.find('data')
                if data is not None and data.get('encoding') == 'csv':
                    # Очищаем холст
                    self.canvas.delete("all")
                    
                    # Получаем данные тайлов
                    tile_data = []
                    for row in data.text.strip().split('\n'):
                        row_data = [int(tile) for tile in row.split(',') if tile.strip()]
                        if row_data:
                            tile_data.append(row_data)
                    
                    # Загружаем тайлсет
                    for tileset in root.findall('tileset'):
                        firstgid = int(tileset.get('firstgid'))
                        source = tileset.get('source')
                        
                        # Если тайлсет встроен в файл
                        image = tileset.find('image')
                        if image is not None:
                            image_path = os.path.join(os.path.dirname(tmx_path), image.get('source'))
                            try:
                                tileset_img = Image.open(image_path)
                                tileset_img = tileset_img.convert('RGBA')
                                
                                # Отображаем тайлы на холсте
                                for y, row in enumerate(tile_data):
                                    for x, tile_id in enumerate(row):
                                        if tile_id != 0:  # 0 означает пустой тайл
                                            # Вычисляем позицию тайла в тайлсете
                                            tile_id -= firstgid
                                            if tile_id >= 0:  # Проверяем, что tile_id валидный
                                                cols = tileset_img.width // tile_width
                                                tile_x = (tile_id % cols) * tile_width
                                                tile_y = (tile_id // cols) * tile_height
                                                
                                                # Вырезаем тайл из тайлсета
                                                tile = tileset_img.crop((tile_x, tile_y, 
                                                                      tile_x + tile_width, 
                                                                      tile_y + tile_height))
                                                
                                                # Преобразуем в формат Tkinter
                                                tile_tk = ImageTk.PhotoImage(tile)
                                                self.image_references.append(tile_tk)  # Сохраняем ссылку
                                                
                                                # Отображаем тайл на холсте
                                                self.canvas.create_image(
                                                    x * tile_width, 
                                                    y * tile_height, 
                                                    image=tile_tk, 
                                                    anchor=tk.NW
                                                )
                                
                            except Exception as e:
                                messagebox.showerror("Ошибка", f"Не удалось загрузить тайлсет: {str(e)}")
                                return
                    
                    messagebox.showinfo("Успех", f"Карта успешно загружена: {os.path.basename(tmx_path)}")
                    return
            
            messagebox.showwarning("Предупреждение", "Не удалось найти данные тайлов в файле")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить файл .tmx: {str(e)}")

    def add_to_recent_blocks(self, block_name):
        """Добавляет блок в список недавних"""
        if not block_name:
            return
            
        if block_name in self.recent_blocks:
            self.recent_blocks.remove(block_name)
            
        self.recent_blocks.insert(0, block_name)
        
        # Keep only the last N blocks
        if len(self.recent_blocks) > self.max_recent_blocks:
            self.recent_blocks = self.recent_blocks[:self.max_recent_blocks]
            
        self.update_recent_blocks_ui()
        
    def update_recent_blocks_ui(self):
        """Обновляет меню недавних блоков"""
        # Clear existing menu
        self.recent_menu.delete(0, tk.END)
        
        if not self.recent_blocks:
            self.recent_menu.add_command(label="Нет недавних блоков", state=tk.DISABLED)
            return
            
        for block_name in self.recent_blocks:
            # Add block name with ellipsis if too long
            display_name = block_name if len(block_name) < 20 else f"{block_name[:17]}..."
            self.recent_menu.add_command(
                label=display_name,
                command=lambda b=block_name: self.select_recent_block(b)
            )
    
    def select_recent_block(self, block_name):
        """Выбирает блок из списка недавних"""
        if block_name in self.blocks:
            self.current_block = block_name
            print(f"[i] Выбран блок: {block_name}")
            return True
        return False

    def load_block(self, filepath=None):
        if not filepath:
            filepath = filedialog.askopenfilename(
                filetypes=[("Изображения", "*.png;*.jpg;*.jpeg"), ("Все файлы", "*.*")]
            )
        
        if not filepath or not os.path.exists(filepath):
            print("❌ Файл не выбран или не существует")
            return None
            
        block_name = os.path.basename(filepath)
        
        # Check if block already exists
        if block_name in self.blocks:
            print(f"[i] Блок '{block_name}' уже загружен")
            self.current_block = block_name
            return self.blocks[block_name]["img"]
            
        try:
            # Open and resize the image
            img = Image.open(filepath)
            img = img.resize((BLOCK_SIZE, BLOCK_SIZE), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage and store
            tk_img = ImageTk.PhotoImage(img)
            
            # Store the image and path
            self.blocks[block_name] = {
                "path": filepath,
                "img": tk_img,
                "tk_img": tk_img  # Keep a reference
            }
            
            self.current_block = block_name
            print(f"[+] Загружен блок: {block_name}")
            
            # Add to recent blocks
            self.add_to_recent_blocks(block_name)
            
            return tk_img
            
        except Exception as e:
            error_msg = f"❌ Ошибка загрузки блока: {str(e)}"
            print(error_msg)
            messagebox.showerror("Ошибка", error_msg)
            return None

    def copy_block(self, event):
        """Копирует блок по нажатию средней кнопки мыши"""
        # Convert screen coordinates to canvas coordinates
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # Find the object at the clicked position
        index = self.find_object_at(x, y)
        if index is not None:
            obj = self.objects[index]
            block_name = obj["block"]
            if block_name in self.blocks:
                # Select the block for copying
                self.current_block = block_name
                print(f"[i] Выбран для копирования: {block_name}")
                # Add to recent blocks
                self.add_to_recent_blocks(block_name)
                # Place a new block at cursor position
                self.place_or_delete_block(event)
    
    def is_position_taken(self, x, y, ignore_index=None):
        for i, obj in enumerate(self.objects):
            if ignore_index is not None and i == ignore_index:
                continue
            if obj["x"] == x and obj["y"] == y:
                return True
        return False

    def find_object_at(self, x, y):
        """Находит объект по координатам с учетом смещения просмотра"""
        for i, obj in enumerate(self.objects):
            obj_x, obj_y = obj["x"], obj["y"]
            # Convert canvas coordinates to view coordinates
            view_x = x - self.view_x
            view_y = y - self.view_y
            if (obj_x - BLOCK_SIZE//2 <= view_x <= obj_x + BLOCK_SIZE//2 and 
                obj_y - BLOCK_SIZE//2 <= view_y <= obj_y + BLOCK_SIZE//2):
                return i
        return None

    def place_or_delete_block(self, event):
        """Создает или удаляет блок при нажатии ПКМ"""
        if not self.current_block:
            print("⚠️ Сначала загрузите блок!")
            return
            
        # Находим ближайшую точку сетки с учетом смещения просмотра
        view_x = event.x + self.view_x
        view_y = event.y + self.view_y
        grid_x = (view_x // BLOCK_SIZE) * BLOCK_SIZE + BLOCK_SIZE // 2
        grid_y = (view_y // BLOCK_SIZE) * BLOCK_SIZE + BLOCK_SIZE // 2
        
        # Проверяем, есть ли уже блок в этой позиции
        index = self.find_object_at(grid_x, grid_y)
        if index is not None:
            # Если есть — удалим блок с canvas и из списка
            obj = self.objects.pop(index)
            self.canvas.delete(obj["canvas_id"])
            print(f"[X] Блок удалён: {obj['block']} на ({obj['x']}, {obj['y']})")
            print(f"[i] Осталось блоков на карте: {len(self.objects)}")
            return

        # Если блока нет — создаём новый (если выбран)
        if self.current_block not in self.blocks:
            print(f"[X] Ошибка: блок '{self.current_block}' не найден в загруженных блоках")
            return
            
        block_data = self.blocks[self.current_block]
        obj_id = self.canvas.create_image(grid_x, grid_y, image=block_data["img"], anchor=tk.CENTER)
        
        self.objects.append({
            "x": grid_x, 
            "y": grid_y, 
            "block": self.current_block, 
            "canvas_id": obj_id,
            "image_reference": block_data["img"]  # Keep reference to prevent garbage collection
        })
        
        print(f"[+] Размещён блок '{self.current_block}' на позиции ({grid_x}, {grid_y})")
        print(f"[i] Всего блоков на карте: {len(self.objects)}")

    def pan_view(self, dx, dy):
        """Перемещает вид на указанное смещение"""
        # Calculate new view position
        new_view_x = self.view_x + dx
        new_view_y = self.view_y + dy
        
        # Constrain to canvas boundaries
        new_view_x = max(0, min(new_view_x, self.canvas_width - CANVAS_WIDTH))
        new_view_y = max(0, min(new_view_y, self.canvas_height - CANVAS_HEIGHT))
        
        # Only update if position changed
        if new_view_x != self.view_x or new_view_y != self.view_y:
            self.view_x = new_view_x
            self.view_y = new_view_y
            
            # Update canvas view
            self.canvas.xview_moveto(self.view_x / self.canvas_width)
            self.canvas.yview_moveto(self.view_y / self.canvas_height)
            
            # Обновляем выделение при панорамировании
            if self.selected_block is not None and self.selected_block < len(self.objects):
                self.select_block(self.selected_block)
    

    def _on_mousewheel(self, event):
        """Обработка колесика мыши для вертикальной прокрутки"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.view_y = self.canvas.canvasy(0)
        self.draw_arrow_indicators()
    
    def _on_shift_mousewheel(self, event):
        """Обработка Shift+колесико для горизонтальной прокрутки"""
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        self.view_x = self.canvas.canvasx(0)
        self.draw_arrow_indicators()
    
    def select_block(self, index):
        """Выделяет блок"""
        self.selected_block = index
        if index is not None:
            # Рисуем рамку выделения
            obj = self.objects[index]
            x, y = obj['x'], obj['y']
            self.canvas.delete('selection_rect')
            self.canvas.create_rectangle(
                x - 25, y - 25, x + 25, y + 25,
                outline='blue', width=2, dash=(4, 4), tags='selection_rect'
            )
    
    def move_block(self, index, new_x, new_y):
        """Перемещает блок на новые координаты"""
        if 0 <= index < len(self.objects):
            obj = self.objects[index]
            
            # Проверяем, не занята ли новая позиция
            if not self.is_position_taken(new_x, new_y, index):
                # Обновляем координаты
                obj['x'] = new_x
                obj['y'] = new_y
                
                # Перемещаем на холсте
                self.canvas.coords(obj['canvas_id'], new_x - self.view_x, new_y - self.view_y)
                
                # Обновляем выделение
                if self.selected_block == index:
                    self.select_block(index)
    
    def start_drag(self, event):
        """Начинает перетаскивание блока или панорамирование"""
        # Проверяем, кликнули ли мы по блоку
        index = self.find_object_at(event.x + self.view_x, event.y + self.view_y)
        if index is not None:
            # Выделяем блок
            self.select_block(index)
            
            # Начинаем перетаскивание
            self.drag_data = {
                "item": index,
                "x": event.x + self.view_x,
                "y": event.y + self.view_y
            }
        else:
            # Убираем выделение
            self.selected_block = None
            self.canvas.delete('selection_rect')
            
            # Начинаем панорамирование
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self.is_panning = True
            self.canvas.config(cursor="fleur")
    
    def pan_canvas(self, event):
        """Обрабатывает панорамирование холста"""
        if self.is_panning:
            # Calculate delta
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            
            # Update view
            self.pan_view(-dx, -dy)
            
            # Update start position for next movement
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            
            # Обновляем выделение при панорамировании
            if self.selected_block is not None and self.selected_block < len(self.objects):
                self.select_block(self.selected_block)
    
    def do_drag(self, event):
        """Перетаскивает блок"""
        if "item" in self.drag_data:
            index = self.drag_data["item"]
            dx = event.x + self.view_x - self.drag_data["x"]
            dy = event.y + self.view_y - self.drag_data["y"]
            
            # Move the block
            self.canvas.move(self.objects[index]["canvas_id"], dx, dy)
            
            # Update position
            self.drag_data["x"] = event.x + self.view_x
            self.drag_data["y"] = event.y + self.view_y
            
            # Update object position
            self.objects[index]["x"] += dx
            self.objects[index]["y"] += dy
    
    def end_drag(self, event):
        """Завершает перетаскивание блока или панорамирование"""
        if self.is_panning:
            self.is_panning = False
            self.canvas.config(cursor="")
        elif "item" in self.drag_data:
            # Update the final position
            index = self.drag_data["item"]
            coords = self.canvas.coords(self.objects[index]["canvas_id"])
            if coords:  # Check if the item still exists
                self.objects[index]["x"] = coords[0]
                self.objects[index]["y"] = coords[1]
        self.drag_data = {}

    def clear_level(self):
        """Очищает текущий уровень"""
        # Clear all objects from canvas
        for obj in self.objects:
            self.canvas.delete(obj["canvas_id"])
        self.objects = []
        self.bg_image = None
        self.bg_path = None
        self.canvas.delete("all")
        print("ℹ️ Уровень очищен")
    
    def load_level(self, filepath=None):
        """Загружает уровень из файла"""
        if not filepath:
            filepath = filedialog.askopenfilename(
                initialdir=os.path.abspath(SAVE_FOLDER),
                title="Выберите файл уровня",
                filetypes=[("Файлы уровня", "*.py"), ("Все файлы", "*.*")]
            )
        
        if not filepath or not os.path.exists(filepath):
            print("❌ Файл не выбран или не существует")
            return False
            
        try:
            # Clear current level
            self.clear_level()
            
            # Load the level file
            level_dir = os.path.dirname(filepath)
            level_globals = {}
            with open(filepath, 'r', encoding='utf-8') as f:
                exec(f.read(), level_globals)
            
            # Set background if exists
            if 'background_image' in level_globals and level_globals['background_image']:
                bg_path = os.path.join(level_dir, level_globals['background_image'])
                if os.path.exists(bg_path):
                    self.bg_path = bg_path
                    self.load_background()
            
            # Load blocks
            if 'objects' in level_globals:
                for obj in level_globals['objects']:
                    block_name = obj['block']
                    x, y = obj['x'], obj['y']
                    
                    # Load block if not already loaded
                    if block_name not in self.blocks:
                        block_path = os.path.join(level_dir, block_name)
                        if os.path.exists(block_path):
                            self.load_block(block_path)
                    
                    # Create block on canvas
                    if block_name in self.blocks:
                        block_data = self.blocks[block_name]
                        obj_id = self.canvas.create_image(x, y, image=block_data["img"], anchor=tk.CENTER)
                        
                        self.objects.append({
                            "x": x,
                            "y": y,
                            "block": block_name,
                            "canvas_id": obj_id,
                            "image_reference": block_data["img"]
                        })
                        
                        # Add to recent blocks
                        self.add_to_recent_blocks(block_name)
            
            print(f"✅ Уровень загружен: {os.path.basename(filepath)}")
            print(f"ℹ️ Загружено объектов: {len(self.objects)}")
            
            # Update window title
            self.root.title(f"Редактор Уровня - {os.path.basename(filepath)}")
            
            return True
            
        except Exception as e:
            error_msg = f"❌ Ошибка при загрузке уровня: {str(e)}"
            print(error_msg)
            messagebox.showerror("Ошибка", error_msg)
            return False
    
    def save_level(self):
        """Сохраняет текущий уровень"""
        # Ensure save directory exists
        os.makedirs(SAVE_FOLDER, exist_ok=True)
        
        # Get level name from user
        level_name = simpledialog.askstring("Сохранение уровня", "Введите название уровня:")
        if not level_name:
            return
            
        if not level_name.endswith('.py'):
            level_name += '.py'
            
        level_py_path = os.path.join(SAVE_FOLDER, level_name)
        bg_name = os.path.basename(self.bg_path) if self.bg_path else None

        with open(level_py_path, "w", encoding="utf-8") as f:
            f.write(f'background_image = {repr(bg_name)}\n\n')
            f.write('objects = [\n')
            for obj in self.objects:
                f.write(f'    {{"x": {obj["x"]}, "y": {obj["y"]}, "block": {repr(obj["block"])}, "solid": True}},\n')
            f.write(']\n')

        if self.bg_path:
            copyfile(self.bg_path, os.path.join(SAVE_FOLDER, bg_name))

        for block_name, block_data in self.blocks.items():
            copyfile(block_data["path"], os.path.join(SAVE_FOLDER, block_name))

        print(f"\n✅ Уровень сохранён в файл: {level_py_path}\n")
        with open(level_py_path, "r", encoding="utf-8") as f:
            print(f.read())


if __name__ == "__main__":
    root = tk.Tk()
    app = LevelEditor(root)
    root.mainloop()
