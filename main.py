import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox, ttk
import fitz
from PIL import Image, ImageTk
import json

class TextInputDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None, initial_text="", initial_size=12):
        self.text = initial_text
        self.size = initial_size
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text="テキスト:").grid(row=0, column=0, sticky="w")
        self.text_entry = tk.Entry(master)
        self.text_entry.insert(0, self.text)  # 初期テキストを設定
        self.text_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(master, text="サイズ:").grid(row=1, column=0, sticky="w")
        self.size_var = tk.IntVar(value=self.size)
        self.size_menu = ttk.Combobox(master, textvariable=self.size_var, values=[8, 10, 12, 14, 16, 18, 20, 24, 28, 32])
        self.size_menu.grid(row=1, column=1, padx=5, pady=5)

        # デフォルトで選択するサイズがリストにあるか確認
        if self.size in self.size_menu['values']:
            self.size_menu.current(self.size_menu['values'].index(self.size))
        else:
            self.size_menu.current(2)  # デフォルトで12を選択

        return self.text_entry

    def apply(self):
        self.text = self.text_entry.get()
        self.size = self.size_var.get()

def open_pdf():
    global doc, current_page, annotations, pdf_image_id
    # PDFファイルを選択
    input_pdf = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if not input_pdf:
        return

    # PDFを開く
    doc = fitz.open(input_pdf)
    page_listbox.delete(0, tk.END)  # リストボックスをクリア
    annotations = {i: [] for i in range(len(doc))}  # 各ページの注釈を初期化

    # 各ページをリストボックスに追加
    for i in range(len(doc)):
        page_listbox.insert(tk.END, f"Page {i + 1}")

    # 最初のページをプレビュー
    current_page = 0
    show_page(current_page)

    # ボタンを有効化
    save_button.config(state=tk.NORMAL)
    next_button.config(state=tk.NORMAL)
    prev_button.config(state=tk.NORMAL)

def show_page(page_number):
    global pdf_image_id
    page = doc[page_number]
    pix = page.get_pixmap()
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    img_tk = ImageTk.PhotoImage(img)

    # キャンバスに画像を表示
    if pdf_image_id is not None:
        canvas.delete(pdf_image_id)  # 既存のPDF画像を削除
    pdf_image_id = canvas.create_image(0, 0, anchor="nw", image=img_tk)
    canvas.image = img_tk  # 参照を保持

    # ページの回転を取得
    rotation = page.rotation

    # 注釈をキャンバスに描画
    for annotation in annotations[page_number]:
        if isinstance(annotation, tuple) and len(annotation) == 4:  # 矩形の場合
            rect = fitz.Rect(annotation)
            # 回転に応じて座標を変換
            if rotation != 0:
                rect = rect.transform(fitz.Matrix(1, 1).prerotate(rotation))
            x0, y0, x1, y1 = rect
            rect_id = canvas.create_rectangle(x0, y0, x1, y1, outline='red')
            canvas.addtag_withtag(f"rect_{rect_id}", rect_id)
        elif isinstance(annotation, tuple):  # テキストの場合
            text, x, y, size = annotation
            text_id = canvas.create_text(x, y, text=text, fill='red', anchor='nw', font=("Arial", size))
            bbox = canvas.bbox(text_id)
            box_id = canvas.create_rectangle(bbox, outline='lightgray', dash=(2, 2))
            canvas.tag_lower(box_id, text_id)
            canvas.addtag_withtag(f"text_{text_id}", text_id)
            canvas.addtag_withtag(f"box_{text_id}", box_id)

    # リストボックスの選択を更新
    page_listbox.selection_clear(0, tk.END)
    page_listbox.selection_set(page_number)
    page_listbox.see(page_number)

def next_page():
    global current_page
    if current_page < len(doc) - 1:
        current_page += 1
        show_page(current_page)

def prev_page():
    global current_page
    if current_page > 0:
        current_page -= 1
        show_page(current_page)

def save_pdf():
    selected_pages = page_listbox.curselection()
    if not selected_pages:
        messagebox.showwarning("警告", "保存するページを選択してください。")
        return

    output_pdf = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
    if not output_pdf:
        return

    # 選択したページを新しいPDFに保存
    writer = fitz.open()
    serializable_annotations = {}
    for page_number in selected_pages:
        writer.insert_pdf(doc, from_page=page_number, to_page=page_number)
        page = writer[-1]  # 最後に追加されたページを取得
        serializable_annotations[page_number] = []
        page_height = page.rect.height
        for item in annotations[page_number]:
            if isinstance(item, fitz.Rect):
                # ページの回転を考慮して座標を保存
                rect = item
                rotation = page.rotation
                if rotation != 0:
                    rect = rect.transform(fitz.Matrix(1, 1).prerotate(-rotation))
                # Y座標を反転
                rect = fitz.Rect(rect.x0, page_height - rect.y1, rect.x1, page_height - rect.y0)
                serializable_annotations[page_number].append((rect.x0, rect.y0, rect.x1, rect.y1))
                page.add_rect_annot(rect)
            elif isinstance(item, tuple):  # テキストの場合
                text, x, y, size = item
                y = page_height - y  # Y座標を反転
                page.insert_text((x, y), text, fontsize=size, color=(1, 0, 0))
                serializable_annotations[page_number].append((text, x, y, size))

    writer.save(output_pdf)
    writer.close()

    # 注釈をJSONファイルに保存
    with open(output_pdf + '.json', 'w') as f:
        json.dump(serializable_annotations, f)

    messagebox.showinfo("完了", f"選択したページを保存しました: {output_pdf}")

def load_annotations(pdf_path):
    global annotations
    json_path = pdf_path + '.json'
    try:
        with open(json_path, 'r') as f:
            annotations = json.load(f)
            # JSONから読み込んだデータを適切な形式に変換
            for page_number, items in annotations.items():
                annotations[int(page_number)] = [
                    (item if isinstance(item, list) else tuple(item)) for item in items
                ]
    except FileNotFoundError:
        annotations = {i: [] for i in range(len(doc))}

def toggle_mode():
    global draw_mode
    modes = ['rectangle', 'line', 'text']
    current_index = modes.index(draw_mode)
    draw_mode = modes[(current_index + 1) % len(modes)]
    mode_button.config(text=f"モード: {draw_mode}")

def start_draw(event):
    global start_x, start_y, draw_id
    start_x, start_y = event.x, event.y
    if draw_mode == 'rectangle':
        draw_id = canvas.create_rectangle(start_x, start_y, start_x, start_y, outline='red')
    elif draw_mode == 'line':
        draw_id = canvas.create_line(start_x, start_y, start_x, start_y, fill='red')
    elif draw_mode == 'text':
        dialog = TextInputDialog(root, "テキスト入力")
        if dialog.text:
            annotations[current_page].append((dialog.text, start_x, start_y, dialog.size))
            text_id = canvas.create_text(start_x, start_y, text=dialog.text, fill='red', anchor='nw', font=("Arial", dialog.size))
            # バウンディングボックスを描画
            bbox = canvas.bbox(text_id)
            box_id = canvas.create_rectangle(bbox, outline='lightgray', dash=(2, 2))
            canvas.tag_lower(box_id, text_id)
            canvas.addtag_withtag(f"text_{text_id}", text_id)
            canvas.addtag_withtag(f"box_{text_id}", box_id)

def draw(event):
    global draw_id, start_x, start_y
    if draw_mode == 'rectangle':
        canvas.coords(draw_id, start_x, start_y, event.x, event.y)
    elif draw_mode == 'line':
        canvas.coords(draw_id, start_x, start_y, event.x, start_y)

def end_draw(event):
    global current_page
    end_x, end_y = event.x, event.y
    if draw_mode == 'rectangle':
        x0, y0 = min(start_x, end_x), min(start_y, end_y)
        x1, y1 = max(start_x, end_x), max(start_y, end_y)
        if x0 == x1 or y0 == y1:
            return  # 矩形が空の場合は無視
        rect = fitz.Rect(x0, y0, x1, y1)
        annotations[current_page].append(rect)
    elif draw_mode == 'line':
        if start_x == end_x:
            return  # 線が空の場合は無視
        rect = fitz.Rect(min(start_x, end_x), start_y - 1, max(start_x, end_x), start_y + 1)
        annotations[current_page].append(rect)

def select_item(event):
    global start_x, start_y, selected_item
    start_x, start_y = event.x, event.y
    # 右クリックで選択モード
    items = canvas.find_overlapping(event.x, event.y, event.x, event.y)
    for item in items:
        if item != pdf_image_id:  # PDF画像は選択しない
            selected_item = item
            canvas.itemconfig(selected_item, outline='blue')
            break

def edit_text(event):
    # テキストオブジェクトの編集
    items = canvas.find_overlapping(event.x, event.y, event.x, event.y)
    for item in items:
        if item != pdf_image_id and "text_" in canvas.gettags(item):
            # テキストオブジェクトを見つけたら編集
            for annotation in annotations[current_page]:
                if isinstance(annotation, tuple):
                    text, x, y, size = annotation
                    bbox = canvas.bbox(item)
                    if bbox and bbox[0] <= event.x <= bbox[2] and bbox[1] <= event.y <= bbox[3]:
                        dialog = TextInputDialog(root, "テキスト編集", initial_text=text, initial_size=size)
                        if dialog.text:
                            annotations[current_page].remove(annotation)
                            annotations[current_page].append((dialog.text, x, y, dialog.size))
                            canvas.itemconfig(item, text=dialog.text, font=("Arial", dialog.size))
                            # バウンディングボックスを更新
                            new_bbox = canvas.bbox(item)
                            box_id = canvas.find_withtag(f"box_{item}")
                            canvas.coords(box_id, new_bbox)
                        break

def move_item(event):
    global start_x, start_y, selected_item
    if selected_item and selected_item != pdf_image_id:
        dx, dy = event.x - start_x, event.y - start_y
        canvas.move(selected_item, dx, dy)
        # バウンディングボックスも一緒に移動
        if "text_" in canvas.gettags(selected_item):
            box_id = canvas.find_withtag(f"box_{selected_item}")
            if box_id:
                canvas.move(box_id, dx, dy)
        start_x, start_y = event.x, event.y

def end_move(event):
    global selected_item
    if selected_item:
        canvas.itemconfig(selected_item, outline='red')
        selected_item = None

def delete_item(event):
    # ダブルクリックで削除
    items = canvas.find_overlapping(event.x, event.y, event.x, event.y)
    for item in items:
        if item != pdf_image_id:  # PDF画像は削除しない
            canvas.delete(item)
            if "text_" in canvas.gettags(item):
                box_id = canvas.find_withtag(f"box_{item}")
                if box_id:
                    canvas.delete(box_id)
            # 注釈リストからも削除する必要があります（ここでは省略）
            break

def edit_rectangle(event):
    # 矩形オブジェクトの編集
    items = canvas.find_overlapping(event.x, event.y, event.x, event.y)
    for item in items:
        if item != pdf_image_id and "rect_" in canvas.gettags(item):
            # 矩形オブジェクトを見つけたら編集
            bbox = canvas.bbox(item)
            if bbox and bbox[0] <= event.x <= bbox[2] and bbox[1] <= event.y <= bbox[3]:
                # ここで編集ダイアログを開くか、サイズ変更を行うロジックを追加
                # 例: 新しい座標を取得して更新する
                new_x0, new_y0, new_x1, new_y1 = bbox  # ここで新しい座標を設定
                canvas.coords(item, new_x0, new_y0, new_x1, new_y1)
                break

# GUIの設定
root = tk.Tk()
root.title("PDFページ選択ツール")

canvas = tk.Canvas(root, width=600, height=800)
canvas.pack(side=tk.LEFT)

draw_mode = 'rectangle'  # 初期モードを矩形に設定
selected_item = None
pdf_image_id = None
mode_button = tk.Button(root, text=f"モード: {draw_mode}", command=toggle_mode)
mode_button.pack(side=tk.TOP, padx=10, pady=20)

canvas.bind("<ButtonPress-1>", start_draw)
canvas.bind("<B1-Motion>", draw)
canvas.bind("<ButtonRelease-1>", end_draw)

# 右クリックで選択と移動
canvas.bind("<ButtonPress-3>", select_item)
canvas.bind("<B3-Motion>", move_item)
canvas.bind("<ButtonRelease-3>", end_move)

# 左ダブルクリックでテキスト編集
canvas.bind("<Double-Button-1>", edit_text)

# 左ダブルクリックで矩形編集
canvas.bind("<Double-Button-3>", edit_rectangle)

page_listbox = tk.Listbox(root, selectmode=tk.MULTIPLE)
page_listbox.pack(side=tk.RIGHT, fill=tk.Y)

open_button = tk.Button(root, text="PDFを開く", command=open_pdf)
open_button.pack(side=tk.TOP, padx=10, pady=20)

prev_button = tk.Button(root, text="前のページ", command=prev_page, state=tk.DISABLED)
prev_button.pack(side=tk.LEFT, padx=10, pady=20)

next_button = tk.Button(root, text="次のページ", command=next_page, state=tk.DISABLED)
next_button.pack(side=tk.RIGHT, padx=10, pady=20)

save_button = tk.Button(root, text="選択したページを保存", command=save_pdf, state=tk.DISABLED)
save_button.pack(side=tk.BOTTOM, padx=10, pady=20)

root.mainloop()
