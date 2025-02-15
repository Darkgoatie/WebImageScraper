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
import urllib.request
import json
from pathlib import Path

configfile = "data/config.json"
def loadJsonConfiguration():
    try:
        with open(configfile, "r") as file:
            configdata = json.load(file)
        return configdata
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load JSON configuration: {e}")
        return {}

def get_video_size(video_url):
    try:
        response = requests.head(video_url, timeout=5)
        response.raise_for_status()
        size_in_bytes = int(response.headers.get('Content-Length', 0))
        size_in_mb = size_in_bytes / (1024 * 1024)  # Convert bytes to MB
        return round(size_in_mb, 2)  # Round to 2 decimal places
    except Exception as e:
        print(f"Failed to get video size: {e}")
        return None

def fetch_image(poster_url, ref):
    try:
        req = urllib.request.Request(
            poster_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        )
        response = urllib.request.urlopen(req)
        return response.read()
    except Exception as e:
        print(f"Failed to load poster image: {e}")
        return None

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

class VideoFrame(ttk.Frame):
    def __init__(self, parent, video_url, checkbox_var, poster_url, video_size):
        super().__init__(parent)  # Correct initialization
        
        self.video_url = video_url
        self.checkbox_var = checkbox_var
        
        # Create an inner frame for the video and overlay
        self.video_container = ttk.Frame(self)
        self.video_container.pack(expand=True, fill="both")

        # Load and display the poster image
        if poster_url:
            try:
                image_data = fetch_image(poster_url)
                if image_data:
                    image = Image.open(BytesIO(image_data))
                    image = image.resize((200, 120), Image.LANCZOS)
                    self.poster_photo = ImageTk.PhotoImage(image)
                image = Image.open(BytesIO(image_data))
                image = image.resize((200, 120), Image.LANCZOS)  # Resize for consistency
                self.poster_photo = ImageTk.PhotoImage(image)

                # Label to display the image
                self.video_label = ttk.Label(self.video_container, image=self.poster_photo)
                self.video_label.pack(expand=True, fill="both")
            except Exception as e:
                print(f"Failed to load poster image: {e}")
                self.video_label = ttk.Label(self.video_container, text="Video Preview", background="lightgray")
                self.video_label.pack(expand=True, fill="both")
        else:
            # If no poster is available, show a placeholder
            self.video_label = ttk.Label(self.video_container, text="Video Preview", background="lightgray")
            self.video_label.pack(expand=True, fill="both")

        # Display video size instead of duration
        self.size_label = ttk.Label(self, text=f"📦 {video_size} MB" if video_size else "📦 Size: Unknown")
        self.size_label.pack()

        # Checkbox overlay
        self.checkbox = ttk.Checkbutton(self.video_container, variable=checkbox_var)
        self.checkbox.place(x=5, y=5)  # Top-left corner

        # Bind click event to select/deselect
        self.video_label.bind("<Button-1>", self.toggle_selection)

    def toggle_selection(self, event=None):
        self.checkbox_var.set(not self.checkbox_var.get())


class ImageScraperUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Darkgoatie's Website Media Scraper")
        self.root.geometry("1200x800")
        self.media = []  # Store both images and videos
        self.checkboxes = []
        self.driver = None
        self.session = requests.Session()
        self.is_processing = False
        self.processed_urls = set()
        self.media_frames = []
        self.configdata = loadJsonConfiguration()

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
        ttk.Button(url_frame, text="Fetch Media", command=self.fetch_media).pack(side="left")

        # Media Type Frame
        media_type_frame = ttk.Frame(self.main_container, padding="5")
        media_type_frame.grid(row=1, column=0, sticky="ew")

        self.media_type = tk.StringVar(value="photos")  # Default to photos
        ttk.Radiobutton(media_type_frame, text="Photos", variable=self.media_type, value="photos").pack(side="left", padx=5)
        ttk.Radiobutton(media_type_frame, text="Videos", variable=self.media_type, value="videos").pack(side="left", padx=5)
        ttk.Radiobutton(media_type_frame, text="Both", variable=self.media_type, value="both").pack(side="left", padx=5)

        # Filter Frame
        filter_frame = ttk.Frame(self.main_container, padding="5")
        filter_frame.grid(row=2, column=0, sticky="ew")

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
        scroll_frame.grid(row=3, column=0, sticky="ew")
        ttk.Label(scroll_frame, text="Scroll Count:").pack(side="left")
        self.scroll_count = ttk.Entry(scroll_frame, width=5)
        self.scroll_count.pack(side="left", padx=5)
        self.scroll_count.insert(0, self.configdata["defaultScrolls"])

        # Do not load images option
        self.do_not_load_images_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.main_container, text="Do not load images", variable=self.do_not_load_images_var).grid(row=4, column=0, sticky="w", padx=5)

        # Create canvas with scrollbar
        canvas_frame = ttk.Frame(self.main_container)
        canvas_frame.grid(row=5, column=0, sticky="nsew")
        self.main_container.grid_rowconfigure(5, weight=1)
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
        control_frame.grid(row=6, column=0, sticky="ew")

        ttk.Button(control_frame, text="Select All", command=self.select_all).pack(side="left", padx=5)
        ttk.Button(control_frame, text="Deselect All", command=self.deselect_all).pack(side="left", padx=5)

        # Add download path entry
        ttk.Label(control_frame, text="Download Path:").pack(side="left", padx=5)
        self.download_path = ttk.Entry(control_frame, width=45)
        self.download_path.pack(side="left", padx=5)
        self.download_path.insert(0, os.path.join(Path.home(), "Downloads" , self.configdata["defaultDownloadDirectory"]))  # Default path

        ttk.Button(control_frame, text="Download Selected", command=self.download_selected).pack(side="left", padx=5)

        # Add a button to edit JSON configuration
        ttk.Button(control_frame, text="Edit Config", command=self.open_json_editor).pack(side="left", padx=5)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.main_container, textvariable=self.status_var, relief="sunken")
        self.status_bar.grid(row=7, column=0, sticky="ew")


    def open_json_editor(self):
        # Create a new top-level window
        self.json_editor_window = tk.Toplevel(self.root)
        self.json_editor_window.title("Edit JSON Configuration")
        self.json_editor_window.geometry("600x400")

        # Create a Text widget to display and edit the JSON data
        self.json_text = tk.Text(self.json_editor_window, wrap="none")
        self.json_text.pack(fill="both", expand=True, padx=10, pady=10)

        # Load the current JSON data into the Text widget
        try:
            with open(configfile, "r") as file:
                json_data = json.load(file)
                self.json_text.insert("1.0", json.dumps(json_data, indent=4))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load JSON data: {e}")
            self.json_editor_window.destroy()
            return

        # Add a Save button to save the changes
        save_button = ttk.Button(self.json_editor_window, text="Save", command=self.save_json_changes)
        save_button.pack(pady=10)

    def save_json_changes(self):
        try:
            # Get the edited JSON data from the Text widget
            json_data = self.json_text.get("1.0", "end-1c")

            # Validate the JSON data
            json.loads(json_data)  # This will raise an error if the JSON is invalid

            # Write the updated JSON data back to the file
            with open(configfile, "w") as file:
                file.write(json_data)

            # Reload the configuration data
            self.configdata = loadJsonConfiguration()

            # Notify the user that the changes were saved successfully
            messagebox.showinfo("Success", "JSON configuration saved successfully!")
            self.json_editor_window.destroy()

        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Invalid JSON data: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save JSON data: {e}")

    def on_mousewheel(self, event):
        if event.num == 4 or event.num == 5:
            delta = -1 if event.num == 5 else 1
        else:
            delta = event.delta // 120
        self.canvas.yview_scroll(-delta, "units")
        return "break"

    def on_window_resize(self, event=None):
        if hasattr(self, 'current_media'):
            self.reorganize_grid()

    def reorganize_grid(self):
        for frame in self.media_frames:
            frame.grid_forget()

        window_width = self.canvas.winfo_width()
        media_width = 220  # Media width + padding
        num_columns = max(1, window_width // media_width)

        for index, frame in enumerate(self.media_frames):
            row = index // num_columns
            col = index % num_columns
            frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

        for i in range(num_columns):
            self.scrollable_frame.grid_columnconfigure(i, weight=1)

    def fetch_media(self):
        url = self.url_entry.get().strip()
        if not url:
            self.status_var.set("Please enter a URL")
            return
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            self.media = []
            self.checkboxes = []
            self.media_frames = []
            self.processed_urls = set()

            self.status_var.set("Loading page...")
            self.root.update()

            self.driver.get(url)
            scroll_count = int(self.scroll_count.get() or "5")
            self.scroll_page(scroll_count)

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "img"))
            )

            media_type = self.media_type.get()
            if media_type in ["photos", "both"]:
                self.fetch_images()
            if media_type in ["videos", "both"]:
                self.fetch_videos()

            self.status_var.set(f"Found {len(self.media)} matching media items")
            self.reorganize_grid()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")

    def fetch_images(self):
        unfilteredimages = self.driver.find_elements(By.TAG_NAME, "img")
        images = list(filter(self.matches_filters, unfilteredimages))
        total_images = len(images)
        processed_count = 0
    
        self.status_var.set(f"Processing {total_images} images...")
        self.root.update()

    # Rest of the fetch_images method remains the same...

        # First, capture a successful image request's headers
        reference_headers = None
        if images:
            try:
                # Execute JavaScript to capture headers from a successful image load
                reference_headers = self.driver.execute_script("""
                    return new Promise((resolve) => {
                        // Create a test image
                        const img = new Image();

                        // Create a fetch observer
                        const observer = new PerformanceObserver((list) => {
                            const entries = list.getEntries();
                            for (const entry of entries) {
                                // Look for successful image loads
                                if (entry.initiatorType === 'img' && entry.duration > 0) {
                                    // Make a test request to get headers
                                    fetch(entry.name, {
                                        method: 'GET',
                                        credentials: 'same-origin'
                                    }).then(response => {
                                        // Get the request headers from the browser
                                        const headers = {};
                                        headers['Referer'] = document.location.href;
                                        headers['Origin'] = window.location.origin;
                                        headers['Host'] = new URL(entry.name).host;
                                        headers['Accept'] = 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8';
                                        headers['Accept-Encoding'] = 'gzip, deflate, br';
                                        headers['Connection'] = 'keep-alive';
                                        headers['User-Agent'] = navigator.userAgent;
                                        resolve(headers);
                                    });
                                }
                            }
                        });
                
                        // Start observing
                        observer.observe({ entryTypes: ['resource'] });

                        // Load the first image to trigger the observation
                        img.src = arguments[0];
                    });
                """, images[0].get_attribute("src"))

                print("Captured reference headers:", json.dumps(reference_headers, indent=2))

            except Exception as e:
                print(f"Error capturing reference headers: {e}")
                reference_headers = {
                    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'User-Agent': self.driver.execute_script('return navigator.userAgent;'),
                    'Referer': self.driver.current_url,
                    'Origin': urllib.parse.urlparse(self.driver.current_url).scheme + '://' + urllib.parse.urlparse(self.driver.current_url).netloc,
                }

        session = requests.Session()
        session.headers.update(reference_headers)

        for img in images:
            if not self.matches_filters(img):
                continue

            img_src = img.get_attribute("src")
            if not img_src or img_src.startswith('data:'):
                continue

            img_src = urllib.parse.urljoin(self.driver.current_url, img_src)
            if img_src in self.processed_urls:
                continue

            self.processed_urls.add(img_src)

            try:
                # Adjust headers for this specific request
                current_headers = reference_headers.copy()
                parsed_url = urllib.parse.urlparse(img_src)

                # Update domain-specific headers
                current_headers['Host'] = parsed_url.netloc
                if parsed_url.netloc != urllib.parse.urlparse(self.driver.current_url).netloc:
                    current_headers['Sec-Fetch-Site'] = 'cross-site'
                else:
                    current_headers['Sec-Fetch-Site'] = 'same-origin'

                if self.do_not_load_images_var.get() == False:
                    # Make the request
                    response = session.get(img_src, headers=current_headers, timeout=5)
                    response.raise_for_status()

                    if "image" not in response.headers.get("Content-Type", ""):
                        continue

                    img_pil = Image.open(BytesIO(response.content))
                    if img_pil.width > 200:
                        ratio = 200 / img_pil.width
                        img_pil = img_pil.resize((200, int(img_pil.height * ratio)))

                    photo = ImageTk.PhotoImage(img_pil)


                if self.do_not_load_images_var.get() == True:
                    img_pil = Image.new("RGB", (200, 200), (255, 255, 255))
                    photo = ImageTk.PhotoImage(img_pil)

                chk_var = tk.BooleanVar()
                self.checkboxes.append(chk_var)

                img_frame = ImageFrame(self.scrollable_frame, photo, chk_var)
                self.media_frames.append(img_frame)
                ttk.Label(img_frame, text=f"Source: {img_src[:50]}...", wraplength=200).pack()

                self.media.append({'type': 'image', 'src': img_src})
                processed_count += 1
                self.status_var.set(f"Processing {processed_count}/{total_images} images...")
                self.root.update()

            except requests.exceptions.HTTPError as errh:
                print(f"HTTP Error for {img_src}: {errh}")
                if hasattr(errh, 'response'):
                    print(f"Response status: {errh.response.status_code}")
                    print("Response headers:")
                    print(json.dumps(dict(errh.response.headers), indent=2))
                continue

            except Exception as e:
                print(f"Error processing image {img_src}: {e}")
                continue

    def fetch_videos(self):
        unfilteredvideos = self.driver.find_elements(By.TAG_NAME, "video")
        videos = list(filter(self.matches_filters, unfilteredvideos))
        total_videos = len(videos)
        processed_count = 0

        self.status_var.set(f"Processing {total_videos} videos...")
        self.root.update()

        for video in videos:
            if not self.matches_filters(video):
                continue

            video_src = video.find_element(By.TAG_NAME, "source").get_attribute("src")
            video_thumbnail = video.get_attribute("poster")

            if not video_src:
                continue

            video_src = urllib.parse.urljoin(self.driver.current_url, video_src)
            if video_src in self.processed_urls:
                continue

            self.processed_urls.add(video_src)

            # Fetch video size
            video_size = get_video_size(video_src)

            chk_var = tk.BooleanVar()
            self.checkboxes.append(chk_var)

            # Create VideoFrame instance with the video size
            video_frame = VideoFrame(self.scrollable_frame, video_src, chk_var, video_thumbnail, video_size)
            self.media_frames.append(video_frame)

            # Add source label below the video
            ttk.Label(video_frame, text=f"Source: {video_src[:50]}...", wraplength=200).pack()

            self.media.append({'type': 'video', 'src': video_src})
            processed_count += 1
            self.status_var.set(f"Processing {processed_count}/{total_videos} videos...")
            self.root.update()

    def matches_filters(self, element):
        class_filter = self.class_filter.get().strip()
        id_filter = self.id_filter.get().strip()
        src_filter = self.src_filter.get().strip()
        
        if class_filter:
            element_class = element.get_attribute("class")
            if not element_class or class_filter not in element_class:
                return False
                
        if id_filter:
            element_id = element.get_attribute("id")
            if not element_id or id_filter not in element_id:
                return False
                
        if src_filter:
            element_src = element.get_attribute("src")
            if not element_src or src_filter not in element_src:
                return False
                
        return True

    def scroll_page(self, scroll_count):
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scrolls_without_change = 0
        max_unchanged_scrolls = 3

        for i in range(int(scroll_count)):
            self.status_var.set(f"Scrolling page... ({i+1}/{scroll_count})")
            self.root.update()

            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)

            new_height = self.driver.execute_script("return document.body.scrollHeight")

            if new_height == last_height:
                scrolls_without_change += 1
                if scrolls_without_change >= max_unchanged_scrolls:
                    self.status_var.set("Reached bottom of page")
                    break
            else:
                scrolls_without_change = 0

            last_height = new_height

            self.driver.execute_script("""
                document.documentElement.scrollTop = 0;
                document.documentElement.scrollTop = document.documentElement.scrollHeight;
            """)
            time.sleep(0.1)

    def select_all(self):
        for chk in self.checkboxes:
            chk.set(True)
    
    def deselect_all(self):
        for chk in self.checkboxes:
            chk.set(False)

    def download_selected(self):
        selected_indices = [i for i, chk in enumerate(self.checkboxes) if chk.get()]
        if not selected_indices:
            messagebox.showinfo("Info", "No media selected")
            return

        download_path = self.download_path.get().strip()
        if not download_path:
            download_path = "downloads"

        try:
            os.makedirs(download_path, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not create directory: {str(e)}")
            return

        # Create a progress bar
        self.progress_bar = ttk.Progressbar(self.main_container, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.grid(row=7, column=0, sticky="ew", pady=5)

        def download_thread():
            downloaded = 0
            skipped = 0
            failed = 0

            # Capture headers from a successful video request
            reference_headers = None
            try:
                # Execute JavaScript to capture headers from a successful video load
                reference_headers = self.driver.execute_script("""
                    return new Promise((resolve) => {
                        // Create a test video element
                        const video = document.createElement('video');

                        // Create a fetch observer
                        const observer = new PerformanceObserver((list) => {
                            const entries = list.getEntries();
                            for (const entry of entries) {
                                // Look for successful video loads
                                if (entry.initiatorType === 'video' && entry.duration > 0) {
                                    // Make a test request to get headers
                                    fetch(entry.name, {
                                        method: 'GET',
                                        credentials: 'same-origin'
                                    }).then(response => {
                                        // Get the request headers from the browser
                                        const headers = {};
                                        headers['Referer'] = document.location.href;
                                        headers['Origin'] = window.location.origin;
                                        headers['Host'] = new URL(entry.name).host;
                                        headers['Accept'] = 'video/mp4,video/webm,video/ogg';
                                        headers['Accept-Encoding'] = 'gzip, deflate, br';
                                        headers['Connection'] = 'keep-alive';
                                        headers['User-Agent'] = navigator.userAgent;
                                        resolve(headers);
                                    });
                                }
                            }
                        });

                        // Start observing
                        observer.observe({ entryTypes: ['resource'] });

                        // Load the first video to trigger the observation
                        video.src = arguments[0];
                        video.load();
                    });
                """, self.media[selected_indices[0]]['src'])

                print("Captured reference headers for video:", json.dumps(reference_headers, indent=2))

            except Exception as e:
                print(f"Error capturing reference headers for video: {e}")

            if not reference_headers:
                # Fallback headers if we couldn't capture real ones
                reference_headers = {
                    'Accept': 'video/mp4,video/webm,video/ogg',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'User-Agent': self.driver.execute_script('return navigator.userAgent;'),
                    'Referer': self.driver.current_url,
                    'Origin': urllib.parse.urlparse(self.driver.current_url).scheme + '://' + urllib.parse.urlparse(self.driver.current_url).netloc,
                }

            session = requests.Session()
            session.headers.update(reference_headers)

            for idx in selected_indices:
                try:
                    media_url = self.media[idx]['src']
                    filename = os.path.basename(urllib.parse.urlparse(media_url).path)
                    if not filename or filename.isspace():
                        filename = f"media_{idx}.{'mp4' if self.media[idx]['type'] == 'video' else 'jpg'}"

                    filepath = os.path.join(download_path, filename)

                    # Check if the file already exists
                    if os.path.exists(filepath):
                        skipped += 1
                        self.status_var.set(f"Skipping {filename}: File already exists")
                        self.root.update()
                        continue

                    # Adjust headers for this specific request
                    current_headers = reference_headers.copy()
                    parsed_url = urllib.parse.urlparse(media_url)

                    # Update domain-specific headers
                    current_headers['Host'] = parsed_url.netloc
                    if parsed_url.netloc != urllib.parse.urlparse(self.driver.current_url).netloc:
                        current_headers['Sec-Fetch-Site'] = 'cross-site'
                    else:
                        current_headers['Sec-Fetch-Site'] = 'same-origin'

                    response = session.get(media_url, headers=current_headers, stream=True, timeout=5)
                    response.raise_for_status()

                    base, ext = os.path.splitext(filepath)
                    counter = 1
                    while os.path.exists(filepath):
                        filepath = f"{base}_{counter}{ext}"
                        counter += 1

                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0

                    self.progress_bar["maximum"] = total_size

                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=self.configdata["videoDownloadChunkSize"]):
                            if chunk:  # filter out keep-alive new chunks
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                # Update progress bar
                                self.progress_bar["value"] = downloaded_size
                                self.status_var.set(f"Downloading {filename}: {downloaded_size / (1024 * 1024):.2f} MB / {total_size / (1024 * 1024):.2f} MB")
                                self.root.update()

                    downloaded += 1

                except Exception as e:
                    print(f"Error downloading {media_url}: {e}")
                    failed += 1

                self.status_var.set(f"Downloaded: {downloaded}, Skipped: {skipped}, Failed: {failed}")
                self.root.update()

            self.progress_bar.grid_forget()  # Hide progress bar after download
            messagebox.showinfo("Download Complete", 
                              f"Successfully downloaded {downloaded} media items\n"
                              f"Skipped {skipped} media items (already exists)\n"
                              f"Failed to download {failed} media items\n"
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
            
            # Enable CDP logging
            chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            
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