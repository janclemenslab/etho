## storage
- sql database to store metadata?
- hdf5 for raw data?
- how to manage backups etc?
- __how to manage data (sound files for playback)?__ 
    + shared directory?
    + centrally? and transmit via rpc
    + push to all nodes?

## user interface
- flask webui on head
    
## process control
- started with pure 0mq-based control with manual while loops sprinkled throughout the code to listen for commands
- switched over to 0rpc and functional approach:
    + remote call functions
        * change behavior - if running throw error - do not stop and start new instance!!
        * abstract `state` property:
            - CAM: `camera.recording`
            - SND: `pygame.mixer.get_busy()`
            - LED: no necessary??
        * abstract `test` method:
            - CAM: try to grab frame(s) and "display"
            - SND: play test sound
            - LED: flash ON-OFF-ON-OFF 
        * other (optional) abstract methods? make this a syle guide with recommended functions:
            - instantiate `stop`, `start`, `info`, `disp`
    + abstract into 0rpc-Server class that literally serves `self` if possible
        * classes need to extend `SelfServer` - this adds a `serve` function that exposes all classes and properties via rpc
        * register default ports for different classes (picamera, sound, LED, backup, status, etc)
        * scan all registered ports to get state
        * set `busy` and `idle` state for each zerorpc server
    + but `zerorpc.Server.serve()` is blocking 
        * as per zerorpc test code spawn as gevent.spawn(server.run)
        * that also allows stopping the server via the client!!
        * add decorator that tests whether the client is running before calling that function?
        * or write a wrapper for client where we keep track of server state and only allow function calls if server is running
    + probably fabric to remotely start/stop 0rpc server
- consider: callback/event based system'
    + remote trigger events to execute functions 
    + reactive (rxPy) framework?
- other:
    + [mitogen](https://mitogen.readthedocs.io)
    + [pushy](https://github.com/pushyrpc/pushy) (not great for long/independently running remote processes)
    + [execnet](http://codespeak.net/execnet/)
    + celery
    + pyro
    + rpyc
- again: how to manage code?
    + shared directory
    + push to all nodes (via github repo?)
    + central - directly call server-side code (using mitogen, execnet) that is on head (that way we wouldn't have to remotely invoke the 0rpc server/client)

# notes
pygame: event system does not work since it relies on display system and we can't init it. so we query queue manually and add sound if empty.

send data via as tuple so we send by value, not by reference. a list of tuples or a tuple of lists won't work - needs to be a tuple of tuples

sudo apt-get install python-rpi.gpio python3-rpi.gpio