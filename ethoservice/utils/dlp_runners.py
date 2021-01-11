runners = dict()

def register_runner(func):
    """Adds func to model_dict Dict[modelname: modelfunc]. For selecting models by string."""
    runners[func.__name__] = func
    return func    


@register_runner  # all functions with this decorator are available as runners via the DLP/runner parameter
def default(log, tracDrv=None):
    """Default runner - will print ball tracker logs and draw rect.

    Args (IMPORTANT - ALL RUNNERS NEED TO HAVE THESE ARGS DO NOT CHANGE THESE):
        log - handle to the ethodrome logger
        tracDrv - handle for fetching messages from the ball tracker
    """
    # need to import here since psychopy can only work in the thread where it's imported
    # importing these outside of the function will results in failure
    import pyglet.app #
    from psychopy import visual, event, core
    from psychopy.visual.windowframepack import ProjectorFramePacker
    win = visual.Window([800,800], monitor="testMonitor", screen=1, units="deg", fullscr=True, useFBO = True)
    framePacker = ProjectorFramePacker(win)

    rect = visual.Rect(win, width=5, height=5, autoLog=None, units='', lineWidth=1.5, lineColor=None,
                        lineColorSpace='rgb', fillColor=[0.0,0.0,0.0], fillColorSpace='rgb', pos=(-10, 0), size=None, ori=0.0, 
                        opacity=1.0, contrast=1.0, depth=0, interpolate=True, name=None, autoDraw=False)

    cnt = 0
    period = 100
    RUN = True
    WHITE = True
    log.info('run')
    while RUN:
        cnt +=1
        if WHITE:
            rect.fillColor = [1.0, 1.0, 1.0]  # advance phase by 0.05 of a cycle
        else:
            rect.fillColor = [-1.0, -1.0, -1.0]  # advance phase by 0.05 of a cycle
        if cnt % period == 0:
            WHITE = not WHITE
            rect.pos = rect.pos + [0.01, 0]
            if tracDrv is not None:
                print(tracDrv._read_message())

        rect.draw()
        win.flip()

        if len(event.getKeys())>0:
            break
        event.clearEvents()
    
    win.close()
    core.quit()
    