# -*- coding: utf-8 -*-
import json
import os
import sys
import tkinter as tk
from tkinter import ttk
from functools import partial
from threading import Thread

if getattr(sys, 'frozen', None):
    basedir = sys._MEIPASS
else:
    basedir = os.path.dirname(__file__)

conf_dir = os.path.join(basedir, "conf")

PY2 = sys.version_info[0] == 2

if PY2:
    import tkMessageBox as messagebox
else:
    from tkinter import messagebox

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
    def __init__(self, text_area):
        self.buffer = text_area

    def write(self, d):
        self.buffer.insert(tk.END, d)


def hello():
    print("使用myss，发现更大的世界！")
    print("请在选择配置文件后, 点击启动代理。如果没有配置文件, 请手动填写各个输入框")
    


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

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.iconbitmap(os.path.join(basedir, "res/favicon.ico"))

    def new_conf_row(self, name, type, label_text, bindvar, values=[], event=None):
        label = ttk.Label(self.conframe,
            text=label_text, font=('Arial', 12),
            width=15,
        )
        if type is ttk.Combobox:
            widget = type(self.conframe,
                width=21, state="readonly",
                textvariable=bindvar, values=values
            )
        else:
            widget = type(self.conframe, width=23, textvariable=bindvar)
        
        if event:
            widget.bind(event.event, event.callback)

        row = Row(label, widget, bindvar)
        self.form.add_row(name, row)

    def divid_frame(self):
        self.conframe = ttk.Frame(self, width=300, height=400)
        self.conframe.pack(side='left')
        self.logframe = ttk.Frame(self, width=400, height=400)
        self.logframe.pack()

    def add_log_area(self):
        ta = tk.Text(self.logframe, width=80, font=("Times New Roman", 11))
        ta.pack()
        self.text_area = ta

    def all_encrypt_method(self):
        return [
            "aes-256-cfb", "aes-128-cfb"
        ]

    def create_widgets(self):
        self.var_conf = tk.StringVar(self.conframe)
        self.new_conf_row(
            "conf", ttk.Combobox, '选择配置文件', 
            self.var_conf, self.get_all_conf(),
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
            self.var_method, self.all_encrypt_method())

        self.var_timeout = tk.IntVar(self.conframe, value=300)
        self.new_conf_row("timeout", ttk.Entry, '超时(秒)', self.var_timeout)

        self.var_proxy_mode = tk.StringVar(self.conframe, value="off")
        self.new_conf_row(
            "proxy_mode", ttk.Combobox, "代理模式", self.var_proxy_mode,
            values=["pac", "global", "off"],
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

    def on_select_proxy_mode(self, *v):
        proxy_mode = self.form.get_bindvar_by_name("proxy_mode").get()
        if proxy_mode == self._prev_proxy_mode:
            return
        msg = "确定要将代理模式从`%s`改为`%s`吗？" % (self._prev_proxy_mode, proxy_mode)
        if self._proxy_started:
            if messagebox.askokcancel("警告", msg):
                from ss.config import set_proxy_mode
                from ss.settings import settings
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
            with open(self.confile(confname), "wb") as f:
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
            self.destroy()
        else:
            if messagebox.askokcancel("警告", msg):
                for func in onexit_callbacks:
                    func()
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
        from ss.settings import settings
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

def set_stdout(text_area):
    import logging
    pipe = StdoutRedirector(text_area)
    logging.basicConfig(stream=pipe)
    sys.stdout = pipe
    sys.stderr = pipe

def main():
    app = Application()
    app.title_text("myss")
    set_stdout(app.text_area)
    hello()
    app.mainloop()

if __name__ == "__main__":

    
    main()
