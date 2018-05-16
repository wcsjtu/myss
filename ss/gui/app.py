# -*- coding: utf-8 -*-
import json
import os
import sys
import base64
import tkinter as tk
from tkinter import ttk
from functools import partial
from threading import Thread
from ss.settings import settings
from ss import utils

if getattr(sys, 'frozen', None):
    basedir = sys._MEIPASS
else:
    basedir = os.path.dirname(__file__)

conf_dir = os.path.join(basedir, "conf")

PY2 = sys.version_info[0] == 2
DEFAULT_PAC = "../config/pac"

if PY2:
    from urllib import urlopen, urlencode
    import tkMessageBox as messagebox
else:
    from tkinter import messagebox
    from urllib.request import urlopen
    from urllib.parse import urlencode

class Row(object):

    def __init__(self, label, widget, bindvar):
        self.label = label
        self.widget = widget
        self.bindvar = bindvar

class Event(object):
    def __init__(self, event, callback):
        self.event = event
        self.callback = callback

class Form(object):
    
    def __init__(self):
        self.rows = []
        self._index = {}    # name, position in rows
        super(Form, self).__init__()

    def add_row(self, name, row):
        self._index[name] = len(self.rows)
        self.rows.append( (name, row) )

    def get_bindvar_by_name(self, name):
        index = self._index[name]
        row = self.rows[index]
        return row[1].bindvar

    def get_label_by_name(self, name):
        index = self._index[name]
        row = self.rows[index]
        return row[1].label

    @property
    def length(self):
        return len(self.rows)


class StdoutRedirector(object):
    def __init__(self, text_area, maxsize=10*1024**2):
        self.buffer = text_area
        self.maxsize = maxsize
        self.current_size = 0

    def write(self, d):
        self.raw_write(d)
        if self.current_size >= self.maxsize:
            self.raw_flush()
            self.raw_write("日志大小超过上限, 已持久化到硬盘!")

    def raw_flush(self):
        return clear_log(self.buffer)

    def raw_write(self, d):
        self.current_size += len(d)
        self.buffer.insert(tk.END, d)
        self.buffer.see(tk.END)


def hello():
    print("使用myss，发现更大的世界！")
    print("请在选择配置文件后, 点击启动代理。如果没有配置文件, 请手动填写各个输入框")
    
def clear_log(textarea):
    logfile = settings.get("log_file") or os.path.join(basedir, "ss.log")
    log = textarea.get("1.0", tk.END)
    log = utils.to_bytes(log)
    with open(logfile, "ab") as f:
        f.write(log)
    textarea.delete("1.0", tk.END)

def get_pacfile():
    default = os.path.join(basedir, DEFAULT_PAC)
    default = os.path.abspath(default)
    path = settings.get("pac", default)
    return os.path.abspath(path)

class Application(tk.Tk):

    def __init__(self):
        tk.Tk.__init__(self)

        self.form = Form()
        self._proxy_started = False
        self._prev_proxy_mode = ""

        self.divid_frame()
        self.create_widgets()
        self.place_widget()
        self.add_save_btn()
        self.add_log_area()        
        self.add_log_ctx_menu()
        self.add_menu()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.iconbitmap(os.path.join(basedir, "res/favicon.ico"))

    def new_conf_row(self, name, type, label_text, bindvar, **kw):

        label = ttk.Label(self.conframe,
            text=label_text, font=('Arial', 12),
            width=15,
        )
        if type is ttk.Combobox:
            optional = {"values": kw.get("values", [])}
            if "state" in kw:
                optional["state"] = kw["state"]
            widget = type(self.conframe,
                width=21,textvariable=bindvar,
                **optional
            )
        else:
            widget = type(self.conframe, width=23, textvariable=bindvar)
        
        if kw.get("event"):
            event = kw["event"]
            widget.bind(event.event, event.callback)

        row = Row(label, widget, bindvar)
        self.form.add_row(name, row)

    def divid_frame(self):
        self.conframe = ttk.Frame(self, width=300, height=400)
        self.conframe.pack(side='left')
        self.logframe = ttk.Frame(self, width=400, height=400)
        self.logframe.pack()

    def add_log_area(self):
        scrollbar = tk.Scrollbar(self.logframe)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        ta = tk.Text(self.logframe, width=80, font=("Times New Roman", 11))
        ta["yscrollcommand"] = scrollbar.set
        ta.pack()
        self.textarea_log = ta

    def add_log_ctx_menu(self):
        self.pop_menu_log = tk.Menu(self.textarea_log, tearoff=0)
        self.pop_menu_log.add_command(label="清除", command=partial(clear_log, self.textarea_log))
        self.textarea_log.bind("<Button-3><ButtonRelease-3>", self.on_rclick_log)
        
    def all_encrypt_method(self):
        return [
            "aes-256-cfb", "aes-128-cfb"
        ]

    def create_widgets(self):
        self.var_conf = tk.StringVar(self.conframe)
        self.new_conf_row(
            "conf", ttk.Combobox, '选择配置文件', 
            self.var_conf, values=self.get_all_conf(),
            event=Event("<<ComboboxSelected>>", self.on_select_conf))
        
        self.var_rhost = tk.StringVar(self.conframe)
        self.new_conf_row("rhost", ttk.Entry, '远程服务器', self.var_rhost)

        self.var_rport = tk.IntVar(self.conframe, value=8388)
        self.new_conf_row("rport", ttk.Entry, '远程端口', self.var_rport)

        self.var_lhost = tk.StringVar(self.conframe, value="127.0.0.1")
        self.new_conf_row("local_address", ttk.Entry, '本地代理IP', self.var_lhost)

        self.var_lport = tk.IntVar(self.conframe, value=1080)
        self.new_conf_row("local_port", ttk.Entry, '本地socks5端口', self.var_lport)
 
        self.var_lhttp_port = tk.IntVar(self.conframe, value=1081)
        self.new_conf_row("local_http_port", ttk.Entry, '本地http端口', self.var_lhttp_port)
 
        self.var_password = tk.StringVar(self.conframe)
        self.new_conf_row("password", ttk.Entry, '密码', self.var_password)

        self.var_method = tk.StringVar(self.conframe)
        self.new_conf_row(
            "method", ttk.Combobox, '加密方式', 
            self.var_method, values=self.all_encrypt_method(),
            state="readonly")

        self.var_timeout = tk.IntVar(self.conframe, value=300)
        self.new_conf_row("timeout", ttk.Entry, '超时(秒)', self.var_timeout)

        self.var_proxy_mode = tk.StringVar(self.conframe, value="off")
        self.new_conf_row(
            "proxy_mode", ttk.Combobox, "代理模式", self.var_proxy_mode,
            values=["pac", "global", "off"], state="readonly",
            event=Event("<<ComboboxSelected>>", self.on_select_proxy_mode)
        )

    def add_save_btn(self):
        self.btn_save = tk.Button(self.conframe,
            text="保存配置", command=self.save_conf,
            font=('Arial', 12),
        )
        self.btn_startop = tk.Button(self.conframe, 
            text="启动代理", command=self.startop_proxy,
            font=('Arial', 12),
        )

        self.btn_save.grid(row=self.form.length, column=0, pady=25)
        self.btn_startop.grid(row=self.form.length, column=1, pady=25)

    def add_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        menu_pacfile = tk.Menu(menubar, tearoff=0, font=('Arial', 10), borderwidth=2, )
        menubar.add_cascade(label="PAC", menu=menu_pacfile)
        menu_pacfile.add_command(label="编辑", command=self.open_pac)
        menu_pacfile.add_command(label="重载", command=self.reload_pac)

        menu_share = tk.Menu(menubar, tearoff=0, font=('Arial', 10), borderwidth=2, )
        menubar.add_cascade(label="分享", menu=menu_share)
        menu_share.add_command(label="显示二维码", command=self.show_qrcode)
        menu_share.add_command(label="复制到剪切板", command=self.copy_conf)

    def place_widget(self):
        for i, row in enumerate(self.form.rows):
            _, widget = row
            widget.label.grid(row=i, column=0)
            widget.widget.grid(row=i, column=1, padx=10, pady=5)

    def title_text(self, text):
        self.title(text)

    def get_all_conf(self):
        if not os.path.exists(conf_dir):
            os.makedirs(conf_dir)
            return []
        return os.listdir(conf_dir)

    def on_rclick_log(self, event):
        try:
            self.pop_menu_log.tk_popup(event.x_root, event.y_root, 0)
        finally:
            self.pop_menu_log.grab_release()

    def on_select_proxy_mode(self, *v):
        proxy_mode = self.form.get_bindvar_by_name("proxy_mode").get()
        if proxy_mode == self._prev_proxy_mode:
            return
        msg = "确定要将代理模式从`%s`改为`%s`吗？" % (self._prev_proxy_mode, proxy_mode)
        if self._proxy_started:
            if messagebox.askokcancel("警告", msg):
                from ss.config import set_proxy_mode
                
                settings["proxy_mode"] = proxy_mode
                set_proxy_mode()
                self._prev_proxy_mode = proxy_mode

    def confile(self, filename):
        return os.path.join(conf_dir, filename)

    def get_cfg_form(self):
        raw_conf = {}
        for name, widget in self.form.rows:
            val = widget.bindvar.get()
            raw_conf[name] = val
        return raw_conf

    def check_cfg_form(self, conf):
        for key, val in conf.items():
            if not val:
                label = self.form.get_label_by_name(key)
                msg = u"%s不能为空" % label.cget("text")
                raise ValueError(msg.encode("utf8"))

    def save_conf(self, show=True):
        raw_conf = self.get_cfg_form()
        try:
            self.check_cfg_form(raw_conf)
            confname = raw_conf.pop("conf")
            confname = confname if confname else "default"
            rhost = raw_conf.pop("rhost")
            rport = raw_conf.pop("rport")
            raw_conf["rhost"] = "%s:%d" % (rhost, rport)
            with open(self.confile(confname), "w") as f:
                json.dump(raw_conf, f)
            if show:
                messagebox.showinfo("通知", "保存成功")
        except Exception as err:
            if show:
                messagebox.showerror("警告", err)
            else:
                raise err
            
    def on_close(self):
        from ss.wrapper import onexit_callbacks
        msg = "代理服务运行中, 确定要关闭吗？"
        if not self._proxy_started:
            self.close_gui()
        else:
            if messagebox.askokcancel("警告", msg):
                for func in onexit_callbacks:
                    func()
                self.close_gui()

    def close_gui(self):
        clear_log(self.textarea_log)
        self.destroy()

    def on_select_conf(self, *v):
        try:
            bindvar = self.form.get_bindvar_by_name("conf")
            val = bindvar.get()
            with open(self.confile(val), "rb") as f:
                raw_conf = json.load(f)

            rhost = raw_conf.pop("rhost")
            rhost, rport = rhost.split(":")
            raw_conf["rhost"] = rhost
            raw_conf["rport"] = int(rport)

            for key, val in raw_conf.items():
                self.form.get_bindvar_by_name(key).set(val)

        except Exception as err:
            messagebox.showerror("警告", err)

    def startop_proxy(self):
        if self._proxy_started:
            self.stop_proxy()
        else:
            self.start_proxy()

    def _start_proxy(self, confile):
        from ss.cli import parse_cli
        from ss.management import run_local
        try:
            parse_cli(["local", "-c", confile])
            t = Thread(target=run_local, name="proxy", args=(None, ))
            t.setDaemon(True)
            t.start()
            self._prev_proxy_mode = settings["proxy_mode"]
            messagebox.showinfo("通知", "成功启动代理服务")
        except Exception as err:
            messagebox.showerror("警告", err)

    def stop_proxy(self):
        from ss.ioloop import IOLoop, TIMEOUT_PRECISION
        IOLoop.current().stop()
        self.btn_startop["state"] = tk.DISABLED
        def cb():
            self.btn_startop["text"] = "启动代理"
            self.btn_startop["state"] = tk.NORMAL
            self._proxy_started = False
            messagebox.showinfo("通知", "代理已停止")

        self.conframe.after(
            (TIMEOUT_PRECISION+1)*1000, cb
        )

    def start_proxy(self):
        try:
            self.save_conf(show=False)
            confname = self.form.get_bindvar_by_name("conf").get()
            self._start_proxy(self.confile(confname))
            self._proxy_started = True
            self.btn_startop["text"] = "停止代理"
        except Exception as err:
            messagebox.showerror("警告", err)
            return

    def open_pac(self):
        pac_dialog = PacDialog()
        pacfile = get_pacfile()
        with open(pacfile, "r") as f:
            pac = f.read()
        pac_dialog.textarea_log.insert(tk.END, pac)
        pac_dialog.textarea_log.edit_modified(False)
        self.grab_set()             # make master be unclickable
        self.wait_window(pac_dialog)
        self.grab_release()

    def reload_pac(self):
        from ss.watcher import Pac
        if self._proxy_started:
            Pac.load()
            messagebox.showinfo("通知", "pac文件重新加载完成")
        else:
            messagebox.showerror("警告", "代理运行时才能重载")

    def show_qrcode(self):
        # conf = self.get_cfg_form()
        # qrdialog = QRcodeDialog(conf)
        # self.grab_set()                 # make master be unclickable
        # self.wait_window(qrdialog)
        # self.grab_release()
        # TODO
        messagebox.showinfo("通知", "敬请期待")

    def copy_conf(self):
        conf = self.get_cfg_form()
        url = QRcodeDialog.ssurl(conf)
        self.clipboard_clear()
        self.clipboard_append(url)
        self.update()
        messagebox.showinfo("通知", "URL已复制到剪切板")
    

class PacDialog(tk.Toplevel):

    def __init__(self):
        tk.Toplevel.__init__(self)
        self.title("编辑pac文件")
        self.setup()
        self.iconbitmap(os.path.join(basedir, "res/favicon.ico"))
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._saved = False

    def setup(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        menubar.add_command(label="保存", command=self.save_pac)

        scrollbar = tk.Scrollbar(self)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        ta = tk.Text(self, width=80, font=("Times New Roman", 11))
        ta["yscrollcommand"] = scrollbar.set
        ta.pack()
        scrollbar.config(command=ta.yview)
        self.textarea_log = ta
        self.textarea_log.bind_class("Text", "<Control-a>", self.on_ctrl_a)
        self.textarea_log.bind_class("Text", "<Control-s>", self.save_pac)
        self.textarea_log.bind_class("Text", "<Control-z>", self.undo_edit)
        self.textarea_log.bind_class("Text", "<Control-y>", self.redo_edit)

    def undo_edit(self, *v):
        try:
            self.textarea_log.edit_undo()
        except:
            pass

    def redo_edit(self, *v):
        try:
            self.textarea_log.edit_redo()
        except:
            pass

    def on_ctrl_a(self, *v):
        self.textarea_log.focus_force()
        self.textarea_log.tag_add("sel","1.0","end")

    def save_pac(self, *v):
        pacfile = get_pacfile()
        text = self.textarea_log.get("1.0", tk.END)
        with open(pacfile, "w") as f:
            f.write(text)

    def on_close(self):
        if not self._saved and self.textarea_log.edit_modified():
            if messagebox.askokcancel("警告", "内容没有保存, 确定要退出？"):
                self.destroy()
        else:
            self.destroy()

class QRcodeDialog(tk.Toplevel):
    def __init__(self, conf):
        self.ssconf = conf
        tk.Toplevel.__init__(self)
        self.title("%s的二维码" % conf["conf"])
        self.iconbitmap(os.path.join(basedir, "res/favicon.ico"))
        self.setup()
        

    def setup(self):
        self.cv = tk.Canvas(self, bg='white')
        self.cv.pack()
        ok, photo = self.generator(self.ssconf)
        if not ok:
            messagebox.showerror("警告", photo)
        else:
            self.cv.create_image(250, 250, image=photo)

    @classmethod
    def ssurl(cls, conf):
        ss = "%(method)s-auth:%(password)s@%(rhost)s:%(rport)s" % conf
        data = b"ss://" + base64.encodestring(utils.to_bytes(ss))
        return data

    @classmethod
    def generator(cls, conf):
        url = "https://chart.googleapis.com/chart"
        data = cls.ssurl(conf)
        payload = {
            "cht": "qr",
            "chs": "200x200",
            "chl": data,
        }
        url = url + "?" + urlencode(payload)
        print(url)
        resp = urlopen(url)
        if resp.code != 200:
            return False, resp.reason
        image = resp.read()
        image_b64 = base64.encodestring(image)
        photo = tk.PhotoImage(data=image_b64)
        return True, photo


def set_stdout(text_area):
    import logging
    pipe = StdoutRedirector(text_area)
    logging.basicConfig(stream=pipe)
    sys.stdout = pipe
    sys.stderr = pipe

def main():
    app = Application()
    app.title_text("myss")
    set_stdout(app.textarea_log)
    hello()
    app.mainloop()

if __name__ == "__main__":

    
    main()
