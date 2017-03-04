
import argparse
import grp
import logging
import os
import pwd

logger = logging.getLogger("tools")

def opimidi_set_permissions():
    parser = argparse.ArgumentParser(description="Set device permissions for opimidi")
    parser.add_argument("--uid", default="root",
                        help="User-id to own the files (default: 'root')")
    parser.add_argument("--gid", default="opimidi",
                        help="User-id to own the files (default: 'opimidi')")
    parser.add_argument("--debug", dest="log_level",
                        action="store_const", const=logging.DEBUG,
                        help="Enable debug logging")
    parser.set_defaults(log_level=logging.INFO)
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level)

    try:
        uid = int(args.uid)
    except ValueError:
        uid = pwd.getpwnam(args.uid).pw_uid

    try:
        gid = int(args.gid)
    except ValueError:
        gid = grp.getgrnam(args.gid).gr_gid

    from .lcd import LCD
    from .input import get_write_files

    lcd = LCD()
    files_to_write = lcd.get_write_files() + get_write_files()
    for path in files_to_write:
        logger.debug("chown %s:%s %s", uid, gid, path)
        os.chown(path, uid, gid)
        logger.debug("chmod 0644s %s", path)
        os.chmod(path, 0o664)

