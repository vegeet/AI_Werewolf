import socket
import threading
import json

HOST = '0.0.0.0'
PORT = 12345

room_id_counter = 0
rooms = {}  # 房间字典：room_id -> {"player_count": 6, "players": {"P1": conn, ...}, "sockets": [conn, ...]}

# 广播房间状态更新
def broadcast_room_update(room_id):
    room = rooms.get(room_id)
    if not room:
        return

    player_status = list(room["players"].keys())

    message = {
        "action": "room_update",
        "players": player_status,
        "player_count": room["player_count"]
    }

    for conn in room["sockets"]:
        try:
            conn.send(json.dumps(message).encode())
        except Exception as e:
            print("广播失败：", e)

# 客户端处理线程
def handle_client(conn, addr):
    global room_id_counter
    try:
        while True:
            data = conn.recv(1024).decode()
            if not data:
                break
            request = json.loads(data)
            action = request.get("action")

            if action == "create_room":
                room_id_counter += 1
                new_room_id = f"Room{room_id_counter}"
                player_count = request["player_count"]

                rooms[new_room_id] = {
                    "player_count": player_count,
                    "players": {"P1": conn},
                    "sockets": [conn]
                }

                response = {
                    "status": "success",
                    "room_id": new_room_id,
                    "player_id": 1
                }
                conn.send(json.dumps(response).encode())

            elif action == "join_room":
                room_id = request.get("room_id")
                room = rooms.get(room_id)

                if room and len(room["players"]) < room["player_count"]:
                    pid = len(room["players"]) + 1
                    player_id = f"P{pid}"
                    room["players"][player_id] = conn
                    room["sockets"].append(conn)

                    response = {
                        "status": "success",
                        "player_id": pid,
                        "player_count": room["player_count"]
                    }
                    conn.send(json.dumps(response).encode())

                    # 广播更新房间状态
                    broadcast_room_update(room_id)
                else:
                    response = {"status": "error", "message": "房间不存在或已满"}
                    conn.send(json.dumps(response).encode())

            elif action == "close_room":
                room_id = request.get("room_id")
                if room_id in rooms:
                    # 通知并断开所有客户端
                    for c in rooms[room_id]["sockets"]:
                        try:
                            c.send(json.dumps({"action": "room_closed"}).encode())
                            c.close()
                        except:
                            pass
                    del rooms[room_id]
                    print(f"[关闭] 房间 {room_id} 已销毁")
                else:
                    print(f"[关闭失败] 房间 {room_id} 不存在")
                # 主动关闭请求者的连接
                break

            else:
                response = {"status": "error", "message": "未知请求"}
                conn.send(json.dumps(response).encode())

    except Exception as e:
        print(f"[错误] 来自 {addr} 的异常：{e}")
    finally:
        conn.close()

# 启动服务器
def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[启动] 服务器已启动，监听端口 {PORT}")
    #
    while True:
        conn, addr = server.accept()
        print(f"[连接] 来自 {addr} 的客户端已连接")
        client_thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        client_thread.start()

if __name__ == "__main__":
    start_server()
