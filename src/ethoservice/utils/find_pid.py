import psutil
import sys
import os

if __name__ == "__main__":
    query = sys.argv[1]
    # `not 'find_pid'` filters out calling script if called from remote
    out = [p.info['pid'] for p in psutil.process_iter(attrs=['pid', 'cmdline'])
           if (query.lower() in str(p.info['cmdline']).lower() and not 'find_pid' in str(p.info['cmdline']).lower())]
    # filter out own (python process)
    print(out)
    out = [pid for pid in out if pid != os.getpid()]
    sys.stdout.write(str(out))
    sys.exit(0)
