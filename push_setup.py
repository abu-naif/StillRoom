"""Generate persistent Web Push keys locally; never commit the data folder."""
import argparse
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlsplit


def setup(directory,contact):
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    url=urlsplit(contact)
    if not ((url.scheme=='mailto' and '@' in url.path) or (url.scheme=='https' and url.hostname and not url.username)):
        raise ValueError('Use a contact such as mailto:you@example.com or https://your-stillroom-domain.')
    directory=Path(directory)
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    if (directory/'webpush.json').exists() or (directory/'vapid-private.pem').exists():
        raise ValueError('Push keys already exist. Keep them: replacing keys would disconnect subscribed devices.')
    key=ec.generate_private_key(ec.SECP256R1())
    public=key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    with os.fdopen(os.open(directory/'vapid-private.pem',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as file:
        file.write(private)
    config={'public_key':base64.urlsafe_b64encode(public).decode().rstrip('='),'private_file':'vapid-private.pem','contact':contact}
    with os.fdopen(os.open(directory/'webpush.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as file:
        json.dump(config,file)
    return config


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contact',required=True,help='mailto:your-email or your public HTTPS origin')
    parser.add_argument('--data-dir',default=str(Path(__file__).resolve().parent/'data'))
    args=parser.parse_args()
    try:
        setup(args.data_dir,args.contact)
    except ImportError:
        raise SystemExit('Install requirements.txt in a Python virtual environment first.')
    except (ValueError,OSError) as error:
        raise SystemExit(str(error))
    print('Web Push keys saved privately. Restart Stillroom, then enable notifications on each device.')
