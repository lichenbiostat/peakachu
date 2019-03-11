#!/usr/bin/env python
from sklearn.externals import joblib
import gc
import pathlib

def main(args):
    import numpy as np
    np.seterr(divide='ignore',invalid='ignore')
    from peakachu import trainUtils
    from scipy.sparse import csr_matrix
    import cooler
    import random
    pathlib.Path(args.output).mkdir(parents=True, exist_ok=True)
    Lib = cooler.Cooler(args.path)
    #resolution = Lib.binsize
    resolution = 10000
    coords = trainUtils.parsebed(args.bedpe,lower=2,res=resolution)
    # train model per chromosome
    positive_class = {}
    negative_class = {}
    for key in Lib.chromnames[:]:
        if key.startswith('chr'):
            chromname=key
        else:
            chromname='chr'+key
        print('collecting from {}'.format(key))
        X = Lib.matrix(balance=True,sparse=True).fetch(key).tocsr() # lower down the memory usage
        R,C = X.nonzero()
        validmask = np.isfinite(X.data) # non-nan
        R,C,data = R[validmask],C[validmask],X.data[validmask]
        X = csr_matrix((data, (R, C)), shape=X.shape)
        del data
        idx = (C-R > 2) & (C-R < 80)
        R,C = R[idx],C[idx]
        clist = coords[chromname]
        try:
            positive_class[chromname] = np.vstack((f for f in trainUtils.buildmatrix(
                                             X,clist,width=args.width)))
            neg_coords = [(r,c) for r,c in zip(R,C)]
            random.shuffle(neg_coords)
            stop = len(clist)
            negative_class[chromname]=np.vstack((f for f in trainUtils.buildmatrix(
                             X,neg_coords[::5],width=args.width,
                             positive=False,stop=stop)))
        except:
            print(chromname, ' failed to gather fts')

    for key in Lib.chromnames[:]:
        if key.startswith('chr'):
            chromname=key
        else:
            chromname='chr'+key
 
        Xtrain = np.vstack((v for k,v in positive_class.items() if k!=chromname))
        Xfake = np.vstack((v for k,v in negative_class.items() if k!=chromname))
        print(chromname,'pos/neg: ',Xtrain.shape[0],Xfake.shape[0])
        model = trainUtils.trainRF(Xtrain,Xfake)

        joblib.dump(model, args.output+'/'+chromname+'.pkl', compress=('xz',3))

