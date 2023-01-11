import cv2
import numpy as np
import os


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
        screen_image_corners = (
            np.array(
                [
                    [0.0, 0.0],  # top left
                    [screen_image_width, 0.0],  # top right
                    [screen_image_width, -screen_image_height],  # bottom right
                    [0.0, -screen_image_height],
                ]  # bottom left
            )
            + np.array([screen_image_width * iscreen, 2 * screen_image_height])
        )
        H, _ = cv2.findHomography(proj_rois[iscreen], screen_image_corners)
        transformation_matrices[iscreen] = H
    return transformation_matrices


def create_warpfile(projection_height: int, projection_width: int, projector_dir: str):
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
    roi_filename = "rois_{}x{}.npy".format(projection_height, projection_width)
    if not os.path.exists(os.path.join(projector_dir, roi_filename)):
        raise FileNotFoundError("ROI file not found: %s" % os.path.join(projector_dir, roi_filename))
    rois = np.load(os.path.join(projector_dir, roi_filename))
    # scale the rois such that bottom left is [-1, -1], top right is [1, 1]
    rois_scaled = np.array(rois, dtype=float)
    rois_scaled[:, :, 0] = (rois[:, :, 0] - (projection_width / 2)) / (projection_width / 2)
    rois_scaled[:, :, 1] = ((projection_height / 2) - rois[:, :, 1]) / (projection_height / 2)
    nb_screens = rois.shape[0]
    frame_height, frame_width = 1 / nb_screens, 1
    # get the transformation matrices
    transformation_matrices = get_transformation_matrices(
        image_height=frame_height, image_width=frame_width, proj_rois=rois_scaled
    )

    # create a warping mesh
    # http://paulbourke.net/dome/warpingfisheye/
    # warped image coordinates: (x,y) varies from [-1,-1] (bottom left) to [1,1] (top right)
    # Note: in Paul Bourke's website, warped coordinates varied from
    #   [-aspect_ratio, -1] (bottom left) to [aspect_ratio,1] (top right),
    #   but for psychpy [-1,-1] to [1,1] works
    # original image coordinates: (u,v) varies from [0,0] (bottom left) to [1,1] (top right)
    # intensities i varies from 0 to 1
    node_x = np.linspace(-1, 1, projection_width, dtype="float32")
    node_y = np.linspace(-1, 1, projection_height, dtype="float32")
    node_grid_x, node_grid_y = np.meshgrid(node_x, node_y)
    node_positions_xy = np.concatenate((node_grid_x.reshape(-1, 1), node_grid_y.reshape(-1, 1)), axis=1)
    mesh_coordinates_uv = np.zeros(node_positions_xy.shape, dtype="float32")
    intensities = np.zeros((node_positions_xy.shape[0], 1), dtype="float32")
    projection_image = np.zeros((projection_height, projection_width), dtype="uint8")
    for iscreen in range(rois_scaled.shape[0]):
        projection_mask = projection_image.copy()
        # get the pixel ids in the roi
        roi_mask = cv2.fillConvexPoly(projection_mask, rois[iscreen], 1)
        roi_node_idx = np.vstack(np.where(roi_mask)).T
        # flip y
        roi_node_idx[:, 0] = projection_height - roi_node_idx[:, 0]
        roi_node_idx_flat = roi_node_idx[:, 0] * projection_width + roi_node_idx[:, 1]
        # get node positions in roi
        roi_node_xy = node_positions_xy[roi_node_idx_flat]
        # convert from euclidean to homogeneous coordinates
        roi_node_xy_h = np.concatenate((roi_node_xy, np.ones((roi_node_xy.shape[0], 1))), axis=1)
        # apply transformation to mesh coordinates
        roi_mesh_uv_h = roi_node_xy_h @ transformation_matrices[iscreen].T
        # convert back to euclidean coordinates
        roi_mesh_uv = roi_mesh_uv_h[:, [0, 1]] / roi_mesh_uv_h[:, [2]]
        mesh_coordinates_uv[roi_node_idx_flat] = roi_mesh_uv
        intensities[roi_node_idx_flat] = 1
    # xyuvi coordinates
    warp_mesh_coordinates = np.concatenate((node_positions_xy, mesh_coordinates_uv, intensities), axis=1)
    # save to file
    warpfile = os.path.join(projector_dir, "warpmesh_{}x{}.data".format(projection_height, projection_width))
    filetype = 2
    with open(os.path.join(projector_dir, warpfile), "w+") as f:
        f.write("%d\n" % (filetype))
        f.write("%d %d\n" % (projection_width, projection_height))
        np.savetxt(f, warp_mesh_coordinates, fmt="%0.5f")

    return warpfile
