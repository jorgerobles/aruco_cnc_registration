import numpy as np
import json

# One-line conversion
data = np.load('../data/endo.npz')
json.dump({k: data[k].tolist() for k in data.files}, open('../output.json', 'w'))