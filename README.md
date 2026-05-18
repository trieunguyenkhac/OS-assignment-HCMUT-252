# AsynapRous - Bài tập 1

Project cài đặt HTTP server nhẹ, reverse proxy, REST routing, xác thực người dùng và ứng dụng chat lai giữa client-server và peer-to-peer cho môn CO3093/CO3094.

## Chạy

Chạy sample app:

```powershell
python start_sampleapp.py --server-ip 127.0.0.1 --server-port 2026
```

Mở giao diện chat trên browser:

```text
http://127.0.0.1:2026/index.html
```

Chạy reverse proxy:

```powershell
python start_proxy.py --server-ip 127.0.0.1 --server-port 8080
```

File `config/proxy.conf` đã có sẵn route:

```text
127.0.0.1:8080 -> 127.0.0.1:2026
```

Vì vậy có thể mở:

```text
http://127.0.0.1:8080/index.html
```

để đi qua proxy tới sample app.

## Chế Độ Non-Blocking

Backend mặc định dùng threading. Muốn chạy backend bằng coroutine:

```powershell
$env:ASYNAPROUS_MODE = "coroutine"
python start_sampleapp.py --server-ip 127.0.0.1 --server-port 2026
```

Các điểm có thể chỉ ra khi demo non-blocking:

- `daemon/backend.py`: dùng `asyncio.start_server()` khi bật chế độ coroutine.
- `daemon/httpadapter.py`: dùng `await reader.readuntil(...)`, `await reader.readexactly(...)`, `await writer.drain()`.
- `peer_server.py`: peer listener dùng `asyncio.start_server()`.
- `peer_client.py`: peer client dùng `await asyncio.open_connection()`.

## Peer-To-Peer

Chạy một peer listener ở terminal khác:

```powershell
python peer_server.py --host 127.0.0.1 --port 9101 --peer-id peer-b
```

Gửi message P2P trực tiếp, không đi qua tracker:

```powershell
python peer_client.py --host 127.0.0.1 --port 9101 --from-peer peer-a --to-peer peer-b --text "hello direct"
```

Peer listener dùng:

- `asyncio.start_server()` để nhận kết nối trực tiếp từ peer khác.
- `await reader.readline()` để nhận message.
- `await writer.drain()` để gửi acknowledgement.

Peer client dùng:

- `await asyncio.open_connection()` để mở kết nối trực tiếp tới peer.
- `await writer.drain()` để gửi message.
- `await reader.readline()` để nhận acknowledgement.

## Xác Thực

Tài khoản mặc định:

- `admin:admin`
- `guest:guest`

Đăng nhập bằng JSON:

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:2026/login" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"username":"admin","password":"admin"}'
```

Hoặc dùng HTTP Basic Auth:

```powershell
$auth = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin"))
Invoke-WebRequest `
  -Uri "http://127.0.0.1:2026/get-list" `
  -Headers @{ Authorization = $auth }
```

Sau khi đăng nhập thành công, server trả `Set-Cookie: sessionid=...`.

## Chat API

Các endpoint cần xác thực:

- `POST /submit-info`: đăng ký peer với `peer_id`, `ip`, `port`.
- `POST /add-list`: tham gia channel với `channel`, tùy chọn `peer_id`.
- `GET|POST /get-list`: lấy danh sách peer đang hoạt động và channel.
- `GET|POST /channels`: lấy danh sách channel.
- `GET|POST /messages`: lấy message của một channel.
- `POST /connect-peer`: kiểm tra thông tin một peer theo `peer_id`.
- `POST /broadcast-peer`: lưu message vào channel và gửi tới các peer trong channel bằng asyncio.
- `POST /send-peer`: lưu direct message và gửi trực tiếp tới peer listener bằng asyncio.

Endpoint nhận message qua HTTP fallback:

- `POST /receive-peer`: nhận direct peer message không cần login.

Frontend ở `www/form.html` tự polling:

```javascript
setInterval(() => fetchMessages().catch(() => {}), 1000);
```

Nghĩa là browser tự gọi:

```text
GET /messages?channel=general
```

mỗi 1 giây để cập nhật giao diện.

## Static Files

HTTP server phục vụ:

- `www/*.html`
- `static/css/*.css`
- `static/images/*`

Đường dẫn `/` được map về:

```text
/index.html
```

## Demo Đề Xuất

1. Chạy sample app ở port `2026`.
2. Chạy proxy ở port `8080`.
3. Mở `http://127.0.0.1:8080/form.html`.
4. Login bằng `admin/admin`.
5. Chạy peer listener:

```powershell
python peer_server.py --host 127.0.0.1 --port 9101 --peer-id peer-b
```

6. Register peer trong UI với:

```text
peer id: peer-b
peer ip: 127.0.0.1
peer port: 9101
```

7. Gửi direct message hoặc broadcast message.

Khi giảng viên hỏi:

- Non-blocking ở đâu: chỉ vào `asyncio.start_server()`, `await reader...`, `await writer.drain()`.
- P2P ở đâu: chỉ vào `peer_server.py` và `peer_client.py`.
