# -*- coding: utf-8 JoseaTeba -*-

import sys
from urllib.parse import parse_qsl

from resources.lib.security import secure_entry
from resources.lib.router import run


params = dict(parse_qsl(sys.argv[2][1:]))

# Solo valid en arranque del addon

if sys.argv[2] == "":
# Solo pedir activación al entrar al addon    
    #if not params.get("action"):
    if not secure_entry():
        sys.exit()

# Ejecutar router del addon
run(params)