from sklearn.cluster import DBSCAN
from sklearn import metrics
import numpy as np
import math, pandas
import matplotlib.image as mpimg
from PIL import Image, ImageFile
import logging
import os.path
from os import path
import sys
ImageFile.LOAD_TRUNCATED_IMAGES = True
from sqlalchemy.orm import Session
import sqlalchemy as sqla
import pandas

sys.path.append(os.path.split(sys.path[0])[0])

from common import config
from common import misc
from common import connections

def build_image_matrix(image_path):
    image_list = []
    name_list = []
    for root, _, files in os.walk(image_path, topdown=True):
        for name in files:
            path = os.path.join(root, name)
            logging.info(name)
            if name.endswith('.JPG'):
                image_list.append(np.array(Image.open(str(os.path.join(root, name)))).flatten())
                name_list.append(name)
    image_matrix = np.hstack(image_list) #done to comply with n_samples x n_features of DBSCAN
    return image_matrix, name_list

def cluster_dbscan(image_matrix, eps, minPts):
    #need to ensure image_matrix is (n_samples, n_features)
    db = DBSCAN(eps=eps, min_samples=minPts).fit(image_matrix)
    core_samples_mask = np.zeros_like(db.labels_, dtype=bool)
    core_samples_mask[db.core_sample_indices_] = True
    labels = db.labels_
    n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise_ = list(labels).count(-1)

    print('Estimated number of clusters: %d' % n_clusters_)
    print('Estimated number of noise points: %d' % n_noise_)
    print("Silhouette Coefficient: %0.3f"
        % metrics.silhouette_score(image_matrix, labels))
    
    return labels, n_clusters_

logging.basicConfig(filename='logs/dbscan.log', filemode='w', level=logging.DEBUG)
#how close each picture is to each other (lower is closer, higher is farther)
epsilon = 0.4
#total number of similar pictures to consider the picture a "core point" in DBSCAN
minimum_points = 9
im_mat, nm_list = build_image_matrix(config.MISSOURIAN_IMAGE_PATH)
labels, clusters = cluster_dbscan(im_mat, epsilon, minimum_points)

session_db_tuple = {}
session_db, session_table = connections.make_db_connection('cluster_sessions')
session_db_tuple['distance_between_points'] = epsilon
session_db_tuple['minimum_points'] = minimum_points
session_db_tuple['num_clusters'] = clusters

result = session_db.execute(session_table.insert().values(session_db_tuple))

data_SQL = sqla.sql.text("""
        SELECT cluster_session_id
        FROM cluster_session
        ORDER BY date_collection_date
        LIMIT 1;
        """)

xmp_data = pandas.read_sql(data_SQL, session_db, params={})
c_s_id = int(list(set(xmp_data)))

results_db, results_table = connections.make_db_connection('cluster_results')
conn = results_db.connect()
conn.execute(
    results_table.insert(),
    [
        dict(
            cluster_session_id=c_s_id,
            photo_path=nm_list[i],
            cluster_number=labels[i],
        )
        for i in range(labels)
    ],
)


