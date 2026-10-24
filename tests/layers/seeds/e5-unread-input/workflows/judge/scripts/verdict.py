import os

import ports

ports.returns({"ready": bool(ports.json(os.environ.get("INPUTS_REQUEST"), "request.schema.json")), "language": os.environ.get("INPUTS_LANGUAGE")})
