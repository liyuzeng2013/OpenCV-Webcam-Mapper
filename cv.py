import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import threading
from flask import Flask, Response
import time
from datetime import datetime
import socket
import sys

class CameraStreamApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("摄像头网络映射工具")
        self.geometry("800x650")
        self.resizable(False, False)

        # 状态变量
        self.port = tk.StringVar(value="5000")
        self.is_streaming = False
        self.camera = None
        self.flask_app = None
        self.flask_thread = None

        # 创建UI组件
        self.create_widgets()

        # 启动预览更新
        self.update_preview()

    def create_widgets(self):
        # 摄像头预览区域
        preview_frame = ttk.LabelFrame(self, text="摄像头预览")
        preview_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.preview_label = ttk.Label(preview_frame, text="等待启动摄像头...")
        self.preview_label.pack(padx=10, pady=10)

        # 控制区域
        control_frame = ttk.LabelFrame(self, text="服务控制")
        control_frame.pack(padx=10, pady=5, fill=tk.X)

        # 端口设置
        ttk.Label(control_frame, text="端口号:").grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)
        self.port_entry = ttk.Entry(control_frame, textvariable=self.port, width=10)
        self.port_entry.grid(row=0, column=1, padx=5, pady=10, sticky=tk.W)

        # 按钮
        self.start_btn = ttk.Button(control_frame, text="启动服务", command=self.start_server)
        self.start_btn.grid(row=0, column=2, padx=10, pady=10)

        self.stop_btn = ttk.Button(control_frame, text="关闭服务", command=self.stop_server, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=3, padx=10, pady=10)

        self.quit_btn = ttk.Button(control_frame, text="退出", command=self.quit_app)
        self.quit_btn.grid(row=0, column=4, padx=10, pady=10)

    def start_server(self):
        # 验证端口输入
        port = self.port.get()
        if not port.isdigit():
            messagebox.showerror("错误", "端口号必须为数字")
            return
        port = int(port)

        # 检查端口是否可用
        if self.is_port_in_use(port):
            messagebox.showerror("错误", f"端口 {port} 已被占用")
            return

        # 初始化摄像头
        self.camera = cv2.VideoCapture(0)
        if not self.camera.isOpened():
            messagebox.showerror("错误", "无法打开摄像头")
            return

        # 创建Flask应用
        self.flask_app = Flask(__name__)
        self.setup_flask_routes()

        # 启动Flask服务线程
        self.is_streaming = True
        self.flask_thread = threading.Thread(target=self.run_flask, args=(port,), daemon=True)
        self.flask_thread.start()

        # 更新按钮状态
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        messagebox.showinfo("成功", f"服务已启动\n访问 http://localhost:{port} 查看摄像头流")

    def stop_server(self):
        self.is_streaming = False
        # 释放摄像头资源
        if self.camera:
            self.camera.release()
            self.camera = None
        # 更新UI状态
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.preview_label.config(text="等待启动摄像头...")
        messagebox.showinfo("成功", "服务已停止")

    def quit_app(self):
        self.stop_server()
        self.destroy()

    def is_port_in_use(self, port):
        """检查端口是否被占用"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    def setup_flask_routes(self):
        """配置Flask路由"""
        @self.flask_app.route('/')
        def index():
            return '''
            <html>
              <head>
                <title>摄像头网络流</title>
                <style>
                  body { font-family: Arial, sans-serif; text-align: center; margin: 20px; }
                  #time { font-size: 20px; margin-bottom: 20px; color: #333; }
                  #video-container { max-width: 800px; margin: 0 auto; border: 2px solid #666; border-radius: 5px; }
                  #video-stream { width: 100%; }
                  #controls { margin-top: 20px; }
                  #stop-btn { padding: 10px 20px; font-size: 16px; background-color: #d9534f; color: white; border: none; border-radius: 5px; cursor: pointer; }
                  #stop-btn:hover { background-color: #c9302c; }
                </style>
              </head>
              <body>
                <div id="time"></div>
                <div id="video-container">
                  <img id="video-stream" src="/video_feed">
                </div>
                <div id="controls">
                  <button id="stop-btn">关闭摄像头流</button>
                </div>
                <script>
                  // 更新时间显示
                  function updateTime() {
                    document.getElementById('time').textContent = new Date().toLocaleString();
                  }
                  updateTime();
                  setInterval(updateTime, 1000);

                  // 关闭按钮事件
                  document.getElementById('stop-btn').addEventListener('click', function() {
                    fetch('/stop_stream')
                      .then(response => {
                        if (response.ok) {
                          window.close();
                        }
                      });
                  });
                </script>
              </body>
            </html>
            '''

        @self.flask_app.route('/video_feed')
        def video_feed():
            return Response(self.generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

        @self.flask_app.route('/stop_stream')
        def stop_stream():
            self.is_streaming = False
            return "Stream stopped"

    def generate_frames(self):
        """生成视频流帧"""
        while self.is_streaming and self.camera:
            success, frame = self.camera.read()
            if not success:
                break
            # 转换为JPEG格式
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.03)  # 控制帧率

    def run_flask(self, port):
        """运行Flask服务"""
        self.flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

    def update_preview(self):
        """更新Tkinter摄像头预览"""
        if self.camera and self.is_streaming:
            success, frame = self.camera.read()
            if success:
                # 转换BGR为RGB格式
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # 调整大小以适应预览窗口
                h, w = frame_rgb.shape[:2]
                preview_w = 760
                preview_h = int(h * (preview_w / w))
                frame_resized = cv2.resize(frame_rgb, (preview_w, preview_h))
                # 转换为Tkinter可用的图像格式
                img = Image.fromarray(frame_resized)
                imgtk = ImageTk.PhotoImage(image=img)
                self.preview_label.imgtk = imgtk
                self.preview_label.config(image=imgtk)
        # 定时更新预览
        self.after(30, self.update_preview)

if __name__ == "__main__":
    app = CameraStreamApp()
    app.mainloop()