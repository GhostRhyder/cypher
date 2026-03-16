import hmac, hashlib
secret = "2NDJbb6ew3dPGeE4P9j62T3sUzsPOY1pfxmnmZ1wjfOAj1DezDNzNUJhnkQ4BYgl"
query = "timestamp=1772827838268"
sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
print(sig)
