from fabric.api import *
env.hosts = ['rpi8', 'rpi3', 'rpi5', 'rpi6', 'rpi7', 'rpi3', 'rpi9']#,  'rpi4']
env.user = 'ncb'
env.warn_only = True
env.password = 'droso123'


def push():
    # local("rsync -avhz ~/Dropbox/code.py/ethoservice ncb@192.168.1.3:~/")
    try:
    	local("mkdir \\\\{0}\\ncb\\code\\ ".format(env.host_string))
    	local("cp -rf C:\\Users\\ncb\\Dropbox\\code.py\\ethodrome \\\\{0}\\ncb\\code\\ ".format(env.host_string))
    	# local("robocopy C:\\Users\\ncb\\Dropbox\\code.py\\ethoservice\\ethoservice //rpi3/ncb/ethoservice /S /XD .git")
    except Exception as e:
    	print(e)
    # with cd('code/ethoservice'):
    #     # run('find -type f  -exec touch {} +')
    #     # run('pip uninstall ethoservice -y')
    #     # run('python setup.py install --force')
    #     # run('pip install -e .')
    #     pass

def install(filename, cmd='conda install'):

    try:
    	local("cp -rf {0} \\\\{1}\\ncb\\".format(filename, env.host_string))
    	# local("robocopy C:\\Users\\ncb\\Dropbox\\code.py\\ethoservice\\ethoservice //rpi3/ncb/ethoservice /S /XD .git")
    except Exception as e:
    	print(e)
    run('{0} ./{1}'.format(cmd, filename))
    run('rm -v ./{0}'.format(filename))

def run_cmd(cmd):
	sudo(cmd)

# def commit():
#     local("git add -p && git commit")
def killpython():
    run('pkill python')


def set_volume():
    run('amixer sset Master 10\%') # for some reason need to set to <100 first to maximize volume
    run('amixer sset Master 100\%') # 248=100%