import socket
import json
import customtkinter as ctk

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 12345

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("狼人杀客户端")
        self.geometry("600x600")
        self.room_id = None
        self.player_count = None
        self.is_host = False

        self.protocol("WM_DELETE_WINDOW", self.on_closing)  # 处理窗口关闭
        self.init_main_ui()

        self.my_player_id = None

    def init_main_ui(self):
        self.frame_main = ctk.CTkFrame(self)
        self.frame_main.pack(pady=50)

        self.label = ctk.CTkLabel(self.frame_main, text="欢迎来到狼人杀")
        self.label.pack(pady=10)

        self.create_btn = ctk.CTkButton(self.frame_main, text="创建房间", command=self.show_player_count_selection)
        self.create_btn.pack(pady=10)

        self.join_btn = ctk.CTkButton(self.frame_main, text="进入房间", command=self.show_join_room_input)
        self.join_btn.pack(pady=10)

    def show_player_count_selection(self):
        self.frame_main.destroy()

        self.frame_select = ctk.CTkFrame(self)
        self.frame_select.pack(pady=50)

        label = ctk.CTkLabel(self.frame_select, text="选择房间人数")
        label.pack(pady=10)

        for num in [6, 8, 12]:
            btn = ctk.CTkButton(self.frame_select, text=f"{num}人", command=lambda n=num: self.create_room(n))
            btn.pack(pady=5)

        back_btn = ctk.CTkButton(self.frame_select, text="返回", command=self.back_to_main_from_select)
        back_btn.pack(pady=10)

    def back_to_main_from_select(self):
        self.frame_select.destroy()
        self.init_main_ui()

    def create_room(self, count):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((SERVER_HOST, SERVER_PORT))
                request = {"action": "create_room", "player_count": count}
                s.send(json.dumps(request).encode())
                response = s.recv(1024).decode()
                data = json.loads(response)

                if data["status"] == "success":
                    self.player_count = count
                    self.room_id = data["room_id"]
                    self.is_host = True
                    self.my_player_id = "P1"

                    self.frame_select.destroy()
                    self.open_room_ui()
                else:
                    print("房间创建失败：", data.get("message", "未知错误"))
        except Exception as e:
            print("连接服务器失败：", e)

    def show_join_room_input(self):
        self.frame_main.destroy()

        self.frame_join = ctk.CTkFrame(self)
        self.frame_join.pack(pady=50)

        label = ctk.CTkLabel(self.frame_join, text="请输入房间号：")
        label.pack(pady=10)

        self.room_entry = ctk.CTkEntry(self.frame_join)
        self.room_entry.pack(pady=5)

        confirm_btn = ctk.CTkButton(self.frame_join, text="确认进入", command=self.join_room)
        confirm_btn.pack(pady=10)

        back_btn = ctk.CTkButton(self.frame_join, text="返回", command=self.back_to_main)
        back_btn.pack()

    def join_room(self):
        room_id_input = self.room_entry.get()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((SERVER_HOST, SERVER_PORT))
                request = {"action": "join_room", "room_id": room_id_input}
                s.send(json.dumps(request).encode())
                response = s.recv(1024).decode()
                data = json.loads(response)

                if data["status"] == "success":
                    self.room_id = room_id_input
                    self.player_count = data.get("player_count", 6)
                    self.is_host = False
                    self.my_player_id = f"P{data.get('player_id', 2)}"

                    self.frame_join.destroy()
                    self.open_room_ui()
                else:
                    print("进入失败：", data.get("message", "未知错误"))
        except Exception as e:
            print("连接服务器失败：", e)

    def open_room_ui(self):
        self.frame_room = ctk.CTkFrame(self)
        self.frame_room.pack(pady=20)

        title = ctk.CTkLabel(self.frame_room, text=f"欢迎来到狼人杀！\n房间号：{self.room_id}",
                             font=ctk.CTkFont(size=16, weight="bold"))
        title.pack(pady=10)


        self.player_frame = ctk.CTkFrame(self.frame_room)
        self.player_frame.pack(pady=10)

        self.set_player_count(self.player_count or 6)

    def set_player_count(self, count):
        for widget in self.player_frame.winfo_children():
            widget.destroy()

        self.ready_status = {}  # 记录每个玩家是否准备
        self.ai_status = {}  # 记录每个位置是否是AI

        for i in range(1, count + 1):
            player_id = f"P{i}"
            is_self = player_id == self.my_player_id

            row = i - 1 if i <= count // 2 else i - 1 - count // 2
            column = 0 if i <= count // 2 else 2

            player_label = ctk.CTkLabel(
                self.player_frame,
                text=player_id,
                font=ctk.CTkFont(size=14),
                fg_color="green" if is_self else "transparent",
                corner_radius=10
            )
            player_label.grid(row=row, column=column, sticky="w", padx=10, pady=2)

            self.ai_status[player_id] = False  # 初始化为非AI

            if self.is_host:
                # 房主可以设置AI
                # TODO 每个玩家旁边都要有对应的准备按钮，一旦被设置为AI就不再显示。
                #  同时如果有真人玩家进入游戏，AI按钮就不可以再调整。
                #  若当前位置有真人玩家，就设置一个头像
                switch = ctk.CTkSwitch(
                    self.player_frame,
                    text="AI",
                    command=lambda pid=player_id: self.toggle_ai_and_refresh(pid)
                )
                switch.grid(row=row, column=column, sticky="e", padx=10)

            # 只为当前玩家显示“准备”按钮
            if is_self:
                ready_btn = ctk.CTkButton(
                    self.player_frame,
                    text="准备",
                    command=lambda pid=player_id: self.set_ready(pid)
                )
                ready_btn.grid(row=row, column=column + 1, padx=5)

            self.ready_status[player_id] = False

        self.info_box = ctk.CTkTextbox(self.player_frame, width=200, height=450)
        self.info_box.grid(row=0, column=1, rowspan=count // 2, padx=10)
        self.info_box.insert("end", "房间已创建，等待玩家加入...\n")
        self.info_box.configure(state="disabled")

    def back_to_main(self):
        self.frame_join.destroy()
        self.init_main_ui()

    def toggle_ai_and_refresh(self, player_id):
        self.toggle_ai(player_id)
        self.update_ai_status_display(player_id)

    def update_ai_status_display(self, player_id):
        status = "AI" if self.ai_status[player_id] else "真人"
        self.info_box.configure(state="normal")
        self.info_box.insert("end", f"{player_id} 设为 {status}\n")
        self.info_box.configure(state="disabled")

    def toggle_ai(self, player_id):
        self.ai_status[player_id] = not self.ai_status[player_id]
        print(f"{player_id} 是 {'AI' if self.ai_status[player_id] else '真人'}")

    def set_ready(self, player_id):
        self.ready_status[player_id] = True
        if self.is_host and player_id == self.my_player_id:
            for pid, is_ai in self.ai_status.items():
                if is_ai:
                    self.ready_status[pid] = True
        self.update_ready_display()

        if all(self.ready_status.values()):
            self.start_game()

    def update_ready_display(self):
        self.info_box.configure(state="normal")
        self.info_box.delete("1.0", "end")
        for pid, status in self.ready_status.items():
            self.info_box.insert("end", f"{pid}：{'已准备' if status else '未准备'}\n")
        self.info_box.configure(state="disabled")


    def on_closing(self):
        # 如果是房主，关闭窗口时通知服务器销毁房间
        if self.is_host and self.room_id:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((SERVER_HOST, SERVER_PORT))
                    request = {"action": "close_room", "room_id": self.room_id}
                    s.send(json.dumps(request).encode())
            except Exception as e:
                print("通知服务器销毁房间失败：", e)

        self.destroy()

    def start_game(self):
        self.info_box.configure(state="normal")
        self.info_box.insert("end", "\n所有玩家已准备，游戏开始！\n")
        self.info_box.configure(state="disabled")
        # TODO: 跳转到真正的游戏界面


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = App()
    app.mainloop()
