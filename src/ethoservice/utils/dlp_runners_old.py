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
    # importing these outside of the function results in failure
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

@register_runner
def d_size_runner(log, tracDrv=None):
    return warper_npz_runner(log,tracDrv, 'meansize_test_descending')

@register_runner
def a_size_runner(log, tracDrv=None):
    return warper_npz_runner(log,tracDrv, 'meansize_test_ascending')

@register_runner
def d_vel_runner(log, tracDrv=None):
    return warper_npz_runner(log,tracDrv, 'vel_test_descending')

@register_runner
def a_vel_runner(log, tracDrv=None):
    return warper_npz_runner(log,tracDrv, 'vel_test_ascending')

@register_runner
def d_noise_runner(log, tracDrv=None):
    return warper_npz_runner(log,tracDrv, 'noise_test_descending')

@register_runner
def a_noise_runner(log, tracDrv=None):
    return warper_npz_runner(log,tracDrv, 'noise_test_ascending')

@register_runner
def test_height_runner(log, tracDrv=None):
    return warper_npz_runner(log,tracDrv, 'noise_test_ascending', stimuli_height=-0.1, test=True)

@register_runner
def a_minisize_runner(log, tracDrv=None):
    return warper_npz_runner(log,tracDrv, 'minimeansize_test_ascending')

@register_runner
def a_mininoise_runner(log, tracDrv=None):
    return warper_npz_runner(log,tracDrv, 'mininoise_test_ascending')

@register_runner
def a_oneminute_runner(log, tracDrv=None):
    return warper_npz_runner(log,tracDrv, 'oneminute_ascending')

@register_runner
def a_widervel_runner(log, tracDrv=None):
    return warper_npz_runner(log,tracDrv, 'wider_vel_ascending')

@register_runner  # all functions with this decorator are available as runners via the DLP/runner parameter
def warper_npz_runner(log, tracDrv=None, stimuli_name='mini_meansize_test_descending',stimuli_height=0,test=False):
    # -*- coding: utf-8 -*-
    """
    runner using warper that loads stimuli information from numpy array
    @author: adrian
    """

    # imports
    import cv2
    import numpy as np
    import os
    from psychopy.visual.windowwarp import Warper
    from psychopy.visual import Window, Circle, Rect
    from psychopy import event, core
    from psychopy.visual.windowframepack import ProjectorFramePacker
    import pycrafter4500

    from scipy.signal import savgol_filter

    # Jan: MOVE THIS ELSEWHERE?
    # functions 
    # function to get transformation matrices
    def get_transformation_matrices(image_height, image_width, proj_rois):
        """
        Get transformation matrices from normalized projection coordinates 
        to normalized image coordinates

        Parameters
        ----------
        image_height : int
            Normalized height of the image (0 to 1).
        image_width : int
            Normalized width of the image (0 to 1).
        proj_rois : numpy.ndarray
            Normalized coordinates of the corners of the roi in the projection.
            Should be nb_screens x 4(corners - clockwise from top-left) x 2(coordinates: y,x)
        Returns
        -------
        transformation_matrices : numpy.ndarray
            Homography matrices which transform normalized projection coordinates 
            to normalized image coordinates. Will be of shape nb_screensx3x3

        """
        nb_screens = proj_rois.shape[0]
        transformation_matrices = np.empty((nb_screens, 3, 3))
        screen_image_height = image_height
        screen_image_width = image_width / nb_screens
        for iscreen in range(nb_screens):
            screen_image_corners = np.array(
                [[0., 0.], #top left
                [screen_image_width, 0.], #top right
                [screen_image_width, -screen_image_height], #bottom right
                [0., -screen_image_height]] #bottom left
                ) + np.array(
                    [screen_image_width*iscreen, 2*screen_image_height])
            H, _ = cv2.findHomography(proj_rois[iscreen], screen_image_corners)
            transformation_matrices[iscreen] = H
        return transformation_matrices

    # Jan: MOVE THIS ELSEWHERE?
    # function to create a warping mesh
    def create_warpfile(projection_height:int, projection_width:int, projector_dir:str):
        """
        Function to create and save a warp mesh file

        Parameters
        ----------
        projection_height : int
            Height of the projection in pixels (eg. 1080).
        projection_width : int
            Width of the projection in pixels (eg. 1920).
        projector_dir : str
            Directory where the roi file is stored and
            where the warp file will be stored

        Returns
        -------
        warpfile : str
            Absolute path to the created warp file. 
            The name of the warpfile will be 
            "warpmesh_{projection_height}x{projection_width}.data" 
            and will be stored under projector_dir

        """
        
        # get the rois
        roi_filename = 'rois_{}x{}.npy'.format(projection_height, projection_width)
        if not os.path.exists(os.path.join(projector_dir, roi_filename)):
            raise Exception("ROI file not found: %s" % 
                            os.path.join(projector_dir, roi_filename))
        rois = np.load(os.path.join(projector_dir, roi_filename))
        # scale the rois such that bottom left is [-1, -1], top right is [1, 1]
        rois_scaled = np.array(rois, dtype=float)
        rois_scaled[:, :, 0] = ((rois[:, :, 0] - (projection_width/2)) / 
                                (projection_width/2))
        rois_scaled[:, :, 1] = (((projection_height/2) - rois[:, :, 1]) / 
                                (projection_height/2))
        nb_screens = rois.shape[0]
        frame_height, frame_width = 1/nb_screens, 1
        # get the transformation matrices
        transformation_matrices = get_transformation_matrices(
            image_height = frame_height, image_width = frame_width, 
            proj_rois = rois_scaled)
        
        # create a warping mesh
        # http://paulbourke.net/dome/warpingfisheye/
        # warped image coordinates: (x,y) varies from [-1,-1] (bottom left) to [1,1] (top right)
        # Note: in Paul Bourke's website, warped coordinates varied from 
        #   [-aspect_ratio, -1] (bottom left) to [aspect_ratio,1] (top right), 
        #   but for psychpy [-1,-1] to [1,1] works
        # original image coordinates: (u,v) varies from [0,0] (bottom left) to [1,1] (top right)
        # intensities i varies from 0 to 1
        node_x = np.linspace(-1, 1, 
                            projection_width, dtype='float32')
        node_y = np.linspace(-1, 1, projection_height, dtype='float32')
        node_grid_x, node_grid_y = np.meshgrid(node_x, node_y)
        node_positions_xy = np.concatenate((node_grid_x.reshape(-1, 1), 
                                            node_grid_y.reshape(-1, 1)), 
                                        axis=1)
        mesh_coordinates_uv = np.zeros(node_positions_xy.shape, dtype='float32')
        intensities = np.zeros((node_positions_xy.shape[0], 1), dtype='float32')
        projection_image = np.zeros(
            (projection_height, projection_width), dtype='uint8')
        for iscreen in range(rois_scaled.shape[0]):
            projection_mask = projection_image.copy()
            # get the pixel ids in the roi
            roi_mask = cv2.fillConvexPoly(
                projection_mask, rois[iscreen], 1)
            roi_node_idx = np.vstack(np.where(roi_mask)).T
            # flip y
            roi_node_idx[:, 0] = projection_height - roi_node_idx[:, 0]
            roi_node_idx_flat = (roi_node_idx[:, 0] * projection_width 
                                + roi_node_idx[:, 1])
            # get node positions in roi
            roi_node_xy = node_positions_xy[roi_node_idx_flat]
            # convert from euclidean to homogeneous coordinates
            roi_node_xy_h = np.concatenate(
                (roi_node_xy, np.ones((roi_node_xy.shape[0], 1))), axis=1)
            # apply transformation to mesh coordinates
            roi_mesh_uv_h = roi_node_xy_h @ transformation_matrices[iscreen].T
            # convert back to euclidean coordinates
            roi_mesh_uv = roi_mesh_uv_h[:, [0, 1]] / roi_mesh_uv_h[:, [2]]
            mesh_coordinates_uv[roi_node_idx_flat] = roi_mesh_uv
            intensities[roi_node_idx_flat] = 1
        # xyuvi coordinates
        warp_mesh_coordinates = np.concatenate(
            (node_positions_xy, mesh_coordinates_uv, intensities), axis=1)
        # save to file
        warpfile = os.path.join(
            projector_dir, 'warpmesh_{}x{}.data'.format(projection_height, 
                                                projection_width))
        filetype = 2
        with open(os.path.join(projector_dir, warpfile), 'w+') as f:
            f.write("%d\n"%(filetype))
            f.write("%d %d\n"%(projection_width, projection_height))
            np.savetxt(f, warp_mesh_coordinates, fmt='%0.5f')
        
        return warpfile

    # sample warping on full sreen mode
    screen_id = 1
    projector_dir = 'Z:/#Data/flyball/projector'
    warpfile = os.path.join(projector_dir, "warpmesh_1140x912.data")
    npzfile = np.load(f'Z:/#Data/flyball/stimuli/{stimuli_name}.npz')
    circle_sizes = npzfile['sizes'][:]
    circle_positions = npzfile['positions'][:]
    if test:
        circle_sizes[:] = 20
        circle_positions[:] = 0


    # led blinker
    led_frame = 180*60
    led_size = 0.3
    led_duration = 180
    led_pos = [-1,-0.3]

    # gray block below fly
    block_size = 100

    # JAN: This is set in DLPZeroService.setup - do we need this here? If so, remove from DLPZeroService
    pycrafter4500.pattern_mode(
        num_pats=3, 
        fps=180, 
        bit_depth=7, 
        led_color=0b111,  # BGR flags
        )

    # main window
    win = Window(monitor='projector', screen=screen_id, units="norm", fullscr=False,
        useFBO = True, size=(912,1140), allowGUI=False)
    # 'light' window below fly
    win2 = Window(monitor='projector', screen=screen_id, units="norm", fullscr=False,
        useFBO = True, size = (block_size,block_size),
        pos=(int(win.size[0]/2)-(block_size/2),int(4*win.size[0]/5)-(block_size/2)),
        allowGUI=False, color=[0.8,0.8,0.8])

    projection_width = win.size[0]
    projection_height = win.size[1]
    print("Resolution", win.size)
    framePacker = ProjectorFramePacker(win)
    
    if warpfile is None:
        warpfile = os.path.join(projector_dir, "warpmesh_{}x{}.data".format(
            projection_height, projection_width))
    if not os.path.exists(warpfile):    
        print("Warp file does not exist. Creating warp file")
        warpfile = create_warpfile(projection_height, projection_width, projector_dir)
    print ("Loading warp data from ", warpfile)

    # create a warper and change projection using warpfile
    warper = Warper(win, warp='warpfile', warpfile = warpfile, 
                    eyepoint = [0.5, 0.5], flipHorizontal = False, 
                    flipVertical = False)

    # see https://discourse.psychopy.org/t/how-to-use-cylindrical-warping/7183/2
    warper.changeProjection(warp='warpfile', warpfile = warpfile, 
                    eyepoint = [0.5, 0.5], flipHorizontal = False, 
                    flipVertical = False)
    print("Warp file loaded successfully. Presenting stimulus")


    ## MOVE THIS INTO ITS OWN FUNCTION
    # stimuli object (a fly)
    circle = Circle(win=win, units = 'norm', size=circle_sizes[0], pos=[-1,stimuli_height], radius=2*1/270,
                autoDraw = True, fillColor = [-1, -1, -1], lineWidth=0)

    # 'led' block for photodiode
    rectangle = Rect(win=win, units = 'norm', size=led_size, pos=led_pos,
                autoDraw = True, fillColor=[-1, -1, -1], lineWidth=0, opacity=1)

    iframe = -1
    while True:
        iframe += 1

        # updates
        if iframe % led_frame == 0:
            rectangle.opacity = 0
        if (iframe-led_duration) % led_frame == 0:
            rectangle.opacity = 1

        circle.size = circle_sizes[iframe]
        circle.pos = [circle_positions[iframe], stimuli_height]
        win.flip()

        # # dskey press handling
        # key_pressed = event.getKeys()
        # if len(key_pressed) > 0:
        #     print("Event: ", key_pressed)
        #     if key_pressed[0] in ['return', 'escape']:
        #         break
        if iframe >= circle_positions.shape[0]-1:
            break
        event.clearEvents()

    # cleanup
    win.close()
    win2.close()
    core.quit()

@register_runner  # all functions with this decorator are available as runners via the DLP/runner parameter
def big_box_runner(log, tracDrv=None, stimuli_name='noise_test_ascending'):
    # -*- coding: utf-8 -*-
    """
    runner using warper that loads stimuli information from numpy array
    @author: adrian
    """

    # imports
    import cv2
    import numpy as np
    import os
    from psychopy.visual.windowwarp import Warper
    from psychopy.visual import Window, Circle, Rect
    from psychopy import event, core
    from psychopy.visual.windowframepack import ProjectorFramePacker
    import pycrafter4500

    from scipy.signal import savgol_filter

    # functions 
    # function to get transformation matrices
    def get_transformation_matrices(image_height, image_width, proj_rois):
        """
        Get transformation matrices from normalized projection coordinates 
        to normalized image coordinates

        Parameters
        ----------
        image_height : int
            Normalized height of the image (0 to 1).
        image_width : int
            Normalized width of the image (0 to 1).
        proj_rois : numpy.ndarray
            Normalized coordinates of the corners of the roi in the projection.
            Should be nb_screens x 4(corners - clockwise from top-left) x 2(coordinates: y,x)
        Returns
        -------
        transformation_matrices : numpy.ndarray
            Homography matrices which transform normalized projection coordinates 
            to normalized image coordinates. Will be of shape nb_screensx3x3

        """
        nb_screens = proj_rois.shape[0]
        transformation_matrices = np.empty((nb_screens, 3, 3))
        screen_image_height = image_height
        screen_image_width = image_width / nb_screens
        for iscreen in range(nb_screens):
            screen_image_corners = np.array(
                [[0., 0.], #top left
                [screen_image_width, 0.], #top right
                [screen_image_width, -screen_image_height], #bottom right
                [0., -screen_image_height]] #bottom left
                ) + np.array(
                    [screen_image_width*iscreen, 2*screen_image_height])
            H, _ = cv2.findHomography(proj_rois[iscreen], screen_image_corners)
            transformation_matrices[iscreen] = H
        return transformation_matrices

    # function to create a warping mesh
    def create_warpfile(projection_height:int, projection_width:int, projector_dir:str):
        """
        Function to create and save a warp mesh file

        Parameters
        ----------
        projection_height : int
            Height of the projection in pixels (eg. 1080).
        projection_width : int
            Width of the projection in pixels (eg. 1920).
        projector_dir : str
            Directory where the roi file is stored and
            where the warp file will be stored

        Returns
        -------
        warpfile : str
            Absolute path to the created warp file. 
            The name of the warpfile will be 
            "warpmesh_{projection_height}x{projection_width}.data" 
            and will be stored under projector_dir

        """
        
        # get the rois
        roi_filename = 'rois_{}x{}.npy'.format(projection_height, projection_width)
        if not os.path.exists(os.path.join(projector_dir, roi_filename)):
            raise Exception("ROI file not found: %s" % 
                            os.path.join(projector_dir, roi_filename))
        rois = np.load(os.path.join(projector_dir, roi_filename))
        # scale the rois such that bottom left is [-1, -1], top right is [1, 1]
        rois_scaled = np.array(rois, dtype=float)
        rois_scaled[:, :, 0] = ((rois[:, :, 0] - (projection_width/2)) / 
                                (projection_width/2))
        rois_scaled[:, :, 1] = (((projection_height/2) - rois[:, :, 1]) / 
                                (projection_height/2))
        nb_screens = rois.shape[0]
        frame_height, frame_width = 1/nb_screens, 1
        # get the transformation matrices
        transformation_matrices = get_transformation_matrices(
            image_height = frame_height, image_width = frame_width, 
            proj_rois = rois_scaled)
        
        # create a warping mesh
        # http://paulbourke.net/dome/warpingfisheye/
        # warped image coordinates: (x,y) varies from [-1,-1] (bottom left) to [1,1] (top right)
        # Note: in Paul Bourke's website, warped coordinates varied from 
        #   [-aspect_ratio, -1] (bottom left) to [aspect_ratio,1] (top right), 
        #   but for psychpy [-1,-1] to [1,1] works
        # original image coordinates: (u,v) varies from [0,0] (bottom left) to [1,1] (top right)
        # intensities i varies from 0 to 1
        node_x = np.linspace(-1, 1, 
                            projection_width, dtype='float32')
        node_y = np.linspace(-1, 1, projection_height, dtype='float32')
        node_grid_x, node_grid_y = np.meshgrid(node_x, node_y)
        node_positions_xy = np.concatenate((node_grid_x.reshape(-1, 1), 
                                            node_grid_y.reshape(-1, 1)), 
                                        axis=1)
        mesh_coordinates_uv = np.zeros(node_positions_xy.shape, dtype='float32')
        intensities = np.zeros((node_positions_xy.shape[0], 1), dtype='float32')
        projection_image = np.zeros(
            (projection_height, projection_width), dtype='uint8')
        for iscreen in range(rois_scaled.shape[0]):
            projection_mask = projection_image.copy()
            # get the pixel ids in the roi
            roi_mask = cv2.fillConvexPoly(
                projection_mask, rois[iscreen], 1)
            roi_node_idx = np.vstack(np.where(roi_mask)).T
            # flip y
            roi_node_idx[:, 0] = projection_height - roi_node_idx[:, 0]
            roi_node_idx_flat = (roi_node_idx[:, 0] * projection_width 
                                + roi_node_idx[:, 1])
            # get node positions in roi
            roi_node_xy = node_positions_xy[roi_node_idx_flat]
            # convert from euclidean to homogeneous coordinates
            roi_node_xy_h = np.concatenate(
                (roi_node_xy, np.ones((roi_node_xy.shape[0], 1))), axis=1)
            # apply transformation to mesh coordinates
            roi_mesh_uv_h = roi_node_xy_h @ transformation_matrices[iscreen].T
            # convert back to euclidean coordinates
            roi_mesh_uv = roi_mesh_uv_h[:, [0, 1]] / roi_mesh_uv_h[:, [2]]
            mesh_coordinates_uv[roi_node_idx_flat] = roi_mesh_uv
            intensities[roi_node_idx_flat] = 1
        # xyuvi coordinates
        warp_mesh_coordinates = np.concatenate(
            (node_positions_xy, mesh_coordinates_uv, intensities), axis=1)
        # save to file
        warpfile = os.path.join(
            projector_dir, 'warpmesh_{}x{}.data'.format(projection_height, 
                                                projection_width))
        filetype = 2
        with open(os.path.join(projector_dir, warpfile), 'w+') as f:
            f.write("%d\n"%(filetype))
            f.write("%d %d\n"%(projection_width, projection_height))
            np.savetxt(f, warp_mesh_coordinates, fmt='%0.5f')
        
        return warpfile

    # sample warping on full sreen mode
    screen_id = 1
    projector_dir = 'Z:/#Data/flyball/projector'
    warpfile = os.path.join(projector_dir, "warpmesh_1140x912.data")
    npzfile = np.load(f'Z:/#Data/flyball/stimuli/{stimuli_name}.npz')
    circle_sizes = npzfile['sizes'][:]
    circle_positions = npzfile['positions'][:]

    # led blinker
    led_frame = 180*3
    led_duration = 180
    led_size = 3.0
    led_pos = [-1,-0.3]

    # gray block below fly
    block_size = 100

    # JAN: This is set in DLPZeroService.setup - do we need this here? If so, remove from DLPZeroService
    pycrafter4500.pattern_mode(
        num_pats=3, 
        fps=180, 
        bit_depth=7, 
        led_color=0b111,  # BGR flags
        )

    # main window
    win = Window(monitor='projector', screen=screen_id, units="norm", fullscr=False,
        useFBO = True, size=(912,1140), allowGUI=False)
    # 'light' window below fly
    # win2 = Window(monitor='projector', screen=screen_id, units="norm", fullscr=False,
    #     useFBO = True, size = (block_size,block_size),
    #     pos=(int(win.size[0]/2)-(block_size/2),int(4*win.size[0]/5)-(block_size/2)),
    #     allowGUI=False, color=[0.8,0.8,0.8])

    projection_width = win.size[0]
    projection_height = win.size[1]
    print("Resolution", win.size)
    framePacker = ProjectorFramePacker(win)
    # framePacker = ProjectorFramePacker(win2)
    
    if warpfile is None:
        warpfile = os.path.join(projector_dir, "warpmesh_{}x{}.data".format(
            projection_height, projection_width))
    if not os.path.exists(warpfile):    
        print("Warp file does not exist. Creating warp file")
        warpfile = create_warpfile(projection_height, projection_width, projector_dir)
    print ("Loading warp data from ", warpfile)
    # create a warper and change projection using warpfile
    warper = Warper(win, warp='warpfile', warpfile = warpfile, 
                    eyepoint = [0.5, 0.5], flipHorizontal = False, 
                    flipVertical = False)

    # see https://discourse.psychopy.org/t/how-to-use-cylindrical-warping/7183/2
    warper.changeProjection(warp='warpfile', warpfile = warpfile, 
                    eyepoint = [0.5, 0.5], flipHorizontal = False, 
                    flipVertical = False)
    print("Warp file loaded successfully. Presenting stimulus")

    # stimuli object (a fly)
    circle = Circle(win=win, units = 'norm', size=circle_sizes[0], pos=[-1,0], radius=2*1/270,
                autoDraw = True, fillColor = [-1, -1, -1], lineWidth=0)

    # 'led' block for photodiode
    rectangle = Rect(win=win, units = 'norm', size=led_size, pos=led_pos,
                autoDraw = True, fillColor=[-1, -1, -1], lineWidth=0, opacity=1)

    iframe = -1
    while True:
        iframe += 1

        # updates
        if iframe % led_frame == 0:
            rectangle.opacity = 0
            # win2.color = [0.8,0.8,0.8]
            win.color = [0,0,0]
        if (iframe-led_duration) % led_frame == 0:
            rectangle.opacity = 1
            win.color = [-1,-1,-1]
            # win2.color = [-1,-1,-1]

        # circle.size = circle_sizes[iframe]
        # circle.pos = [circle_positions[iframe], 0]
        win.flip()
        # win2.flip()

        # dskey press handling
        key_pressed = event.getKeys()
        if len(key_pressed) > 0:
            print("Event: ", key_pressed)
            if key_pressed[0] in ['return', 'escape']:
                break
        event.clearEvents()

    # cleanup
    win.close()
    # win2.close()
    core.quit()
