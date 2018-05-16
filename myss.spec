# -*- mode: python -*-
import os
block_cipher = None
pwd = os.getcwd()

a = Analysis(['gui.py'],
             pathex=[pwd],
             binaries=[],
             datas=[
                 ('ss/gui/res/favicon.ico', './res'), ('ss/config/pac', 'config/')
             ],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='myss',
          debug=False,
          strip=False,
          upx=True,
          console=False , icon='ss\\gui\\res\\favicon.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='myss')
