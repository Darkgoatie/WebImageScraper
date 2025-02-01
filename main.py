import tkinter as tk
from tkinter import ttk, messagebox
import requests
from PIL import Image, ImageTk
from io import BytesIO
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os
import threading

class ImageFrame(ttk.Frame):
    def __init__(self, parent, image, checkbox_var, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.checkbox_var = checkbox_var
        
        # Create an inner frame for the image and overlay
        self.image_container = ttk.Frame(self)
        self.image_container.pack(expand=True, fill="both")
        
        # Create the image label
        self.image_label = ttk.Label(self.image_container, image=image)
        self.image_label.image = image  # Keep a reference
        self.image_label.pack(expand=True, fill="both")
        
        # Create a checkbutton with transparent background
        style = ttk.Style()
        style.configure("Transparent.TCheckbutton", background="white")
        self.checkbox = ttk.Checkbutton(
            self.image_container,
            variable=checkbox_var,
            style="Transparent.TCheckbutton"
        )
        self.checkbox.place(x=5, y=5)  # Position at top-left corner
        
        # Bind click events to the entire frame
        self.image_label.bind("<Button-1>", self.toggle_selection)
        
    def toggle_selection(self, event=None):
        self.checkbox_var.set(not self.checkbox_var.get())

class ImageScraperUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Darkgoatie's Website Image Scraper")
        self.root.geometry("1000x800")
        self.images = []
        self.checkboxes = []
        self.driver = None
        self.session = requests.Session()
        self.is_processing = False
        self.processed_urls = set()
        self.image_frames = []
        
        self.create_ui()
        self.setup_browser()

        self.root.bind('<Configure>', self.on_window_resize)

    def create_ui(self):
        # Main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.grid(row=0, column=0, sticky="nsew")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # URL Frame
        url_frame = ttk.Frame(self.main_container, padding="5")
        url_frame.grid(row=0, column=0, sticky="ew")
        ttk.Label(url_frame, text="Website URL:").pack(side="left")
        self.url_entry = ttk.Entry(url_frame, width=50)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(url_frame, text="Fetch Images", command=self.fetch_images).pack(side="left")

        # Filter Frame
        filter_frame = ttk.Frame(self.main_container, padding="5")
        filter_frame.grid(row=1, column=0, sticky="ew")
        
        ttk.Label(filter_frame, text="Filter by:").pack(side="left")
        
        self.class_filter = ttk.Entry(filter_frame, width=15)
        ttk.Label(filter_frame, text="Class:").pack(side="left")
        self.class_filter.pack(side="left", padx=5)
        
        self.id_filter = ttk.Entry(filter_frame, width=15)
        ttk.Label(filter_frame, text="ID:").pack(side="left")
        self.id_filter.pack(side="left", padx=5)
        
        self.src_filter = ttk.Entry(filter_frame, width=15)
        ttk.Label(filter_frame, text="Src contains:").pack(side="left")
        self.src_filter.pack(side="left", padx=5)

        # Scroll Frame
        scroll_frame = ttk.Frame(self.main_container, padding="5")
        scroll_frame.grid(row=2, column=0, sticky="ew")
        ttk.Label(scroll_frame, text="Scroll Count:").pack(side="left")
        self.scroll_count = ttk.Entry(scroll_frame, width=5)
        self.scroll_count.pack(side="left", padx=5)
        self.scroll_count.insert(0, "5")

        # Create canvas with scrollbar
        canvas_frame = ttk.Frame(self.main_container)
        canvas_frame.grid(row=3, column=0, sticky="nsew")
        self.main_container.grid_rowconfigure(3, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Bind mouse wheel events
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind_all("<Button-4>", self.on_mousewheel)
        self.canvas.bind_all("<Button-5>", self.on_mousewheel)

        # Control buttons frame
        control_frame = ttk.Frame(self.main_container, padding="5")
        control_frame.grid(row=4, column=0, sticky="ew")
        
        control_frame = ttk.Frame(self.main_container, padding="5")
        control_frame.grid(row=4, column=0, sticky="ew")
        
        ttk.Button(control_frame, text="Select All", command=self.select_all).pack(side="left", padx=5)
        ttk.Button(control_frame, text="Deselect All", command=self.deselect_all).pack(side="left", padx=5)
        
        # Add download path entry
        ttk.Label(control_frame, text="Download Path:").pack(side="left", padx=5)
        self.download_path = ttk.Entry(control_frame, width=30)
        self.download_path.pack(side="left", padx=5)
        self.download_path.insert(0, "downloads")  # Default path
        
        ttk.Button(control_frame, text="Download Selected", command=self.download_selected).pack(side="left", padx=5)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.main_container, textvariable=self.status_var, relief="sunken")
        self.status_bar.grid(row=5, column=0, sticky="ew")

    def on_mousewheel(self, event):
        if event.num == 4 or event.num == 5:
            delta = -1 if event.num == 5 else 1
        else:
            delta = event.delta // 120
        self.canvas.yview_scroll(-delta, "units")
        return "break"

    def on_window_resize(self, event=None):
        if hasattr(self, 'current_images'):
            self.reorganize_grid()

    def reorganize_grid(self):
        for frame in self.image_frames:
            frame.grid_forget()

        window_width = self.canvas.winfo_width()
        image_width = 220  # Image width + padding
        num_columns = max(1, window_width // image_width)

        for index, frame in enumerate(self.image_frames):
            row = index // num_columns
            col = index % num_columns
            frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

        for i in range(num_columns):
            self.scrollable_frame.grid_columnconfigure(i, weight=1)

    def fetch_images(self):
        url = self.url_entry.get().strip()
        if not url:
            self.status_var.set("Please enter a URL")
            return
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            self.images = []
            self.checkboxes = []
            self.image_frames = []
            self.processed_urls = set()

            self.status_var.set("Loading page...")
            self.root.update()

            self.driver.get(url)
            scroll_count = int(self.scroll_count.get() or "5")
            self.scroll_page(scroll_count)

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "img"))
            )

            images = self.driver.find_elements(By.TAG_NAME, "img")
            total_images = len(images)
            processed_count = 0

            self.status_var.set(f"Processing {total_images} images...")
            self.root.update()

            for img in images:
                if not self.matches_filters(img):
                    continue
                    
                img_src = img.get_attribute("src")
                if not img_src or img_src.startswith('data:'):
                    continue

                img_src = urllib.parse.urljoin(url, img_src)
                if img_src in self.processed_urls:
                    continue

                self.processed_urls.add(img_src)

                try:
                    response = requests.get(img_src, timeout=3)
                    response.raise_for_status()

                    if "image" not in response.headers.get("Content-Type", ""):
                        continue

                    img_pil = Image.open(BytesIO(response.content))
                    if img_pil.width > 200:
                        ratio = 200 / img_pil.width
                        img_pil = img_pil.resize((200, int(img_pil.height * ratio)))

                    photo = ImageTk.PhotoImage(img_pil)

                    chk_var = tk.BooleanVar()
                    self.checkboxes.append(chk_var)

                    # Create ImageFrame instance
                    img_frame = ImageFrame(self.scrollable_frame, photo, chk_var)
                    self.image_frames.append(img_frame)

                    # Add source label below the image
                    ttk.Label(img_frame, text=f"Source: {img_src[:50]}...", wraplength=200).pack()

                    self.images.append({'src': img_src})
                    processed_count += 1
                    self.status_var.set(f"Processing {processed_count}/{total_images} images...")
                    self.root.update()
                    
                except requests.exceptions.HTTPError as errh:
                    if response.status_code == 404:
                        print(f"Skipping: {img_src} (404 Not Found)")
                    else:
                        print(f"HTTP Error: {errh}")
                        
                except Exception as e:
                    print(f"Error processing image {img_src}: {e}")
                    continue

            self.status_var.set(f"Found {len(self.images)} matching images")
            self.reorganize_grid()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")

    def matches_filters(self, img_element):
        class_filter = self.class_filter.get().strip()
        id_filter = self.id_filter.get().strip()
        src_filter = self.src_filter.get().strip()
        
        if class_filter:
            img_class = img_element.get_attribute("class")
            if not img_class or class_filter not in img_class:
                return False
                
        if id_filter:
            img_id = img_element.get_attribute("id")
            if not img_id or id_filter not in img_id:
                return False
                
        if src_filter:
            img_src = img_element.get_attribute("src")
            if not img_src or src_filter not in img_src:
                return False
                
        return True

    def scroll_page(self, scroll_count):
        """
        Scroll the page to the bottom, ensuring all content is loaded.
        Uses both manual scrolling and JavaScript methods for maximum coverage.
        """
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scrolls_without_change = 0
        max_unchanged_scrolls = 3  # Number of times to try scrolling with no height change before stopping

        for i in range(int(scroll_count)):
            self.status_var.set(f"Scrolling page... ({i+1}/{scroll_count})")
            self.root.update()

            # Try multiple scrolling methods
            # 1. Scroll to bottom using JavaScript
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # 3. Final scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # Wait for dynamic content to load
            time.sleep(2)

            # Check if the page height has changed
            new_height = self.driver.execute_script("return document.body.scrollHeight")

            if new_height == last_height:
                scrolls_without_change += 1
                if scrolls_without_change >= max_unchanged_scrolls:
                    self.status_var.set("Reached bottom of page")
                    break
            else:
                scrolls_without_change = 0

            last_height = new_height

            # Try to trigger any lazy loading
            self.driver.execute_script("""
                document.documentElement.scrollTop = 0;
                document.documentElement.scrollTop = document.documentElement.scrollHeight;
            """)

            # Additional wait for any final loading
            time.sleep(1)

    def select_all(self):
        for chk in self.checkboxes:
            chk.set(True)
    
    def deselect_all(self):
        for chk in self.checkboxes:
            chk.set(False)

    def download_selected(self):
        selected_indices = [i for i, chk in enumerate(self.checkboxes) if chk.get()]
        if not selected_indices:
            messagebox.showinfo("Info", "No images selected")
            return

        # Get download path from entry
        download_path = self.download_path.get().strip()
        if not download_path:
            download_path = "downloads"  # Fallback to default
            
        # Create directory if it doesn't exist
        try:
            os.makedirs(download_path, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not create directory: {str(e)}")
            return

        def download_thread():
            downloaded = 0
            failed = 0
            for idx in selected_indices:
                try:
                    img_url = self.images[idx]['src']
                    response = requests.get(img_url, timeout=5)
                    response.raise_for_status()
                    
                    filename = os.path.basename(urllib.parse.urlparse(img_url).path)
                    if not filename or filename.isspace():
                        filename = f"image_{idx}.jpg"
                    
                    filepath = os.path.join(download_path, filename)  # Use custom path
                    
                    base, ext = os.path.splitext(filepath)
                    counter = 1
                    while os.path.exists(filepath):
                        filepath = f"{base}_{counter}{ext}"
                        counter += 1
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    downloaded += 1
                    
                except Exception as e:
                    print(f"Error downloading {img_url}: {e}")
                    failed += 1
                
                self.status_var.set(f"Downloaded: {downloaded}, Failed: {failed}")
                self.root.update()
            
            messagebox.showinfo("Download Complete", 
                              f"Successfully downloaded {downloaded} images\n"
                              f"Failed to download {failed} images\n"
                              f"Location: {os.path.abspath(download_path)}")

        threading.Thread(target=download_thread, daemon=True).start()

    def setup_browser(self):
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.status_var.set("Browser initialized successfully")
        except Exception as e:
            self.status_var.set(f"Error initializing browser: {str(e)}")

    def on_closing(self):
        if self.driver:
            self.driver.quit()
        self.session.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageScraperUI(root)
    root.mainloop()