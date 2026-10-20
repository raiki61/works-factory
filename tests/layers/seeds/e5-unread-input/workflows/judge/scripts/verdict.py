import os

import ports

ports.returns({"ready": bool(ports.json(os.environ.get("INPUTS_REQUEST"))), "language": os.environ.get("INPUTS_LANGUAGE")})
