from __future__ import division, print_function
import numpy as np
import matplotlib.pyplot as plt
import astropy.io.fits as pyfits
import glob
import scipy.optimize as op
import scipy.signal as sig
import time
import multiprocessing
plt.ion()

def gauss_line(p,x):
    return p[0]*np.exp(-(x-p[1])**2/(2*p[2]**2))

def gauss_line_resid(p,x,y, gain=1.0, rnoise=3.0):
    return (gauss_line(p,x) - y)/10. #np.sqrt(np.maximum(y,0) + rnoise**2)

def scipy_gauss_line( args ):
    """
    Fit a Gaussian to data y(x)
    
    Parameters
    ----------
    args: tuple
        nline, guess_center, width_guess, xfit, yfit
    
    Notes
    -----
    nline: int
        index of this line
    guess_center: float
        initial guess position
    """
    fit = op.least_squares(gauss_line_resid, [args[4][args[1]], args[1], args[2]], method='lm', \
            xtol=1e-04, ftol=1e-4, f_scale=[3.,1.,1.], args=(args[3], args[4]))
    if fit.x[2]<0.5: #This is unphysical!
        return args[0], fit.x[1], 0., fit.x[2], 0.
    else:
        cov = np.linalg.inv(fit.jac.T.dot(fit.jac))
        return args[0], fit.x[1], 1/cov[1,1], fit.x[2], 1/cov[2,2]

MIN_PEAK=20
WAVE = np.arange(6400.0,7000.0,0.25)
ddir = '/Volumes/MyPassport/data/wifes/20190225_red/'
fns = np.sort(glob.glob(ddir + '*p11.fits'))
pas = []
mjds = []
xcs = []
xc_sigs = []
xws = []
xw_sigs = []
for f in fns:
    ff = pyfits.open(f)
    pas.append(ff[0].header['TELPAN'])
    mjds.append(ff[0].header['MJD-OBS'])
    dd = ff[0].data[:,8:-8,13:-2]
    
    #Subtract off local sky contribution
    meds = np.median(dd.reshape(dd.shape[0], dd.shape[1]*dd.shape[2]), axis=1).reshape(dd.shape[0],1,1)
    dd -= meds
    
    #Find the maxima in every column.
    max_ix = np.argmax(dd, axis=1)
    maxs = np.max(dd, axis=1)
    
    #Prepare our result arrays
    xc_mn = np.zeros_like(maxs)
    xc_ivar = np.zeros_like(maxs)
    xw_mn = np.zeros_like(maxs)
    xw_ivar = np.zeros_like(maxs)
    xfit = np.arange(dd.shape[1])
    
    #Now prepare the data
    jobs = []
    for ii in range(dd.shape[0]):
        for jj in range(dd.shape[2]):
            if maxs[ii,jj] > MIN_PEAK:
                jobs.append( (ii*dd.shape[2]+jj,max_ix[ii,jj], 2.0, xfit, dd[ii,:,jj]) )
    
    print('Running jobs for file: ' + f)
    then = time.time()
    with multiprocessing.Pool(None) as mypool:
        results = mypool.imap_unordered(scipy_gauss_line,jobs,4) 
        # Process the results
        for r in results:
            xc_mn[r[0]//dd.shape[2],r[0] % dd.shape[2]] = r[1]
            xc_ivar[r[0]//dd.shape[2],r[0] % dd.shape[2]] = r[2]
            xw_mn[r[0]//dd.shape[2],r[0] % dd.shape[2]] = r[3]
            xw_ivar[r[0]//dd.shape[2],r[0] % dd.shape[2]] = r[4]
#    for j in jobs:
#        j0, xc, ivar = scipy_gauss_line(j)
#        xc_mn[j[0]//dd.shape[2],j[0] % dd.shape[2]] = xc
#        xc_ivar[j[0]//dd.shape[2],j[0] % dd.shape[2]] = ivar
    print('Total time: {:5.2f}s'.format(time.time()-then))
    xcs.append(np.sum(xc_mn*xc_ivar, axis=1)/np.sum(xc_ivar, axis=1))
    xc_sigs.append(1./np.sqrt(np.sum(xc_ivar, axis=1)))
    xws.append(np.sum(xw_mn*xw_ivar, axis=1)/np.sum(xw_ivar, axis=1))
    xw_sigs.append(1./np.sqrt(np.sum(xw_ivar, axis=1)))

xcs = np.array(xcs)
xc_sigs = np.array(xc_sigs)
xws = np.array(xws)
xw_sigs = np.array(xw_sigs)

good = np.where(np.median(xc_sigs, axis=1) < 0.06)[0]
pas = np.array(pas)[good]
mjds = np.array(mjds)[good]
xcs = xcs[good]
xc_sigs = xc_sigs[good]
xws = xws[good]
xw_sigs = xw_sigs[good]
filt_xcs = xcs - sig.medfilt(xcs,(1,201))
sign = (2*(pas==150)-1).reshape(len(pas),1)

plt.figure(2)
plt.clf()
plt.plot(WAVE, np.sum(filt_xcs*sign/np.sum(np.abs(sign))*500., axis=0))
plt.axis([6400,6700,-30,30])
plt.xlabel(r'Wavelength ($\AA$)')
plt.ylabel('Offset (mas)')
plt.tight_layout()