import numpy as np
import matplotlib.pyplot as plt
import argparse
from basis import *
from limiter import *

# SSPRK3 coefficients
ark = np.array([0.0, 3.0/4.0, 1.0/3.0])
brk = 1.0 - ark

sqrt3 = np.sqrt(3.0)

# Get arguments
parser = argparse.ArgumentParser()
parser.add_argument('-ncell', type=int, help='Number of cells', default=50)
parser.add_argument('-degree', type=int, help='Polynomial degree', default=1)
parser.add_argument('-cfl', type=float, help='CFL number', default=0.9)
parser.add_argument('-Tf', type=float, help='Final time', default=1.0)
parser.add_argument('-plot_freq', type=int, help='Frequency to plot solution', 
                    default=1)
parser.add_argument('-ic', choices=('sod'), help='Initial condition', 
                    default='sod')
parser.add_argument('-limit', choices=('no','yes'), help='Apply limiter', 
                    default='no')
parser.add_argument('-tvbM', type=float, help='TVB M parameter', default=0.0)
args = parser.parse_args()

# Select initial condition
if args.ic == 'sod':
    from sod import *
else:
    print('Unknown initial condition')
    exit()

k  = args.degree      # polynomial degree
cfl= args.cfl/(2*k+1) # cfl number
nc = args.ncell       # number of cells

nd = k + 1 # dofs per cell
dx = (xmax - xmin)/nc
Mdx2 = args.tvbM * dx**2

# k+1 point gauss rule, integrates exactly upto degree 2*k+1
xg, wg = np.polynomial.legendre.leggauss(k+1)

# Construct Vandermonde matrix for gauss points
Vf = np.zeros((nd,nd))
Vg = np.zeros((nd,nd))
for i in range(nd):
    for j in range(nd):
        Vf[i,j] = shape_value(j, xg[i])
        Vg[i,j] = shape_grad (j, xg[i])

# Construct Vandermonde matrix for uniform points
# uniform points in cell for plotting
nu = np.max([2,k+1])
xu = np.linspace(-1.0,+1.0,nu)
Vu = np.zeros((nu,k+1))
for i in range(nu):
    for j in range(k+1):
        Vu[i,j] = shape_value(j, xu[i])

# Initialize plot
def init_plot(ax,rho,mom,ene):
    lines = []
    umin, umax = 1.0e20, -1.0e20
    for i in range(nc):
        xc = xmin + i*dx + 0.5*dx # cell center
        x  = xc + 0.5*dx*xu       # transform gauss points to cell
        f  = Vu.dot(rho[i,:])
        line, = ax.plot(x,f)
        lines.append(line)
        umin = np.min([umin, f.min()])
        umax = np.max([umax, f.max()])
    plt.title('Initial condition')
    plt.xlabel('x'); plt.ylabel('u'); plt.grid(True)
    plt.axis([xmin,xmax,umin-0.1,umax+0.1])
    plt.draw(); plt.pause(0.1)
    return lines

# Update plot
def update_plot(lines,t,rho):
    umin, umax = 1.0e20, -1.0e20
    for i in range(nc):
        xc = xmin + i*dx + 0.5*dx # cell center
        x  = xc + 0.5*dx*xu       # transform gauss points to cell
        f  = Vu.dot(rho[i,:])
        lines[i].set_ydata(f)
        umin = np.min([umin, f.min()])
        umax = np.max([umax, f.max()])
    plt.axis([xmin,xmax,umin-0.1,umax+0.1])
    plt.title(str(nc)+' cells, Deg = '+str(k)+', CFL = '+str(cfl)+
              ', t = '+('%.3e'%t))
    plt.draw(); plt.pause(0.1)

# Allocate solution variables
rho0 = np.zeros((nc,nd)) # solution at n
rho1 = np.zeros((nc,nd)) # solution at n+1
mom0 = np.zeros((nc,nd)) # solution at n
mom1 = np.zeros((nc,nd)) # solution at n+1
ene0 = np.zeros((nc,nd)) # solution at n
ene1 = np.zeros((nc,nd)) # solution at n+1
resr = np.zeros((nc,nd)) # mass residual
resm = np.zeros((nc,nd)) # momentum residual
rese = np.zeros((nc,nd)) # energy residual

# Set initial condition by L2 projection
for i in range(nc):
    xc = xmin + i*dx + 0.5*dx # cell center
    x  = xc + 0.5*dx*xg       # transform gauss points to cell
    rho,mom,ene = initial_condition(x)
    for j in range(nd):
        rho1[i,j] = 0.5 * rho.dot(Vf[:,j]*wg)
        mom1[i,j] = 0.5 * mom.dot(Vf[:,j]*wg)
        ene1[i,j] = 0.5 * ene.dot(Vf[:,j]*wg)

# plot initial condition
fig = plt.figure()
ax = fig.add_subplot(111)
lines = init_plot(ax,rho1,mom1,ene1)
wait = raw_input("Press enter to continue ")

it, t = 0, 0.0
dt  = cfl*dx/max_speed(rho1,mom1,ene1)
Tf  = args.Tf
lam = dt/dx
while t < Tf:
    if t+dt > Tf:
        dt = Tf - t
        lam = dt/dx
    rho0[:,:] = rho1
    mom0[:,:] = mom1
    ene0[:,:] = ene1
    for rk in range(3):
        # Loop over cells and compute cell integral
        for i in range(nc):
            xc = xmin + i*dx + 0.5*dx # cell center
            x  = xc + 0.5*dx*xg       # transform gauss points to cell
            rho = Vf.dot(rho1[i,:])   # solution at gauss points
            mom = Vf.dot(mom1[i,:])   # solution at gauss points
            ene = Vf.dot(ene1[i,:])   # solution at gauss points
            frho,fmom,fene = flux(rho,mom,ene) # flux at gauss points
            for j in range(nd):
                resr[i,j] = -frho.dot(Vg[:,j]*wg)
                resm[i,j] = -fmom.dot(Vg[:,j]*wg)
                rese[i,j] = -fene.dot(Vg[:,j]*wg)
        # First face
        rhol = rho1[0,:].dot(Vu[0,:])
        rhor = rho1[0,:].dot(Vu[0,:])
        moml = mom1[0,:].dot(Vu[0,:])
        momr = mom1[0,:].dot(Vu[0,:])
        enel = ene1[0,:].dot(Vu[0,:])
        ener = ene1[0,:].dot(Vu[0,:])
        f  = numflux([rhol,moml,enel],[rhor,momr,ener])
        resr[0,:] -= f[0]*Vu[0,:] # Add to first cell
        resm[0,:] -= f[1]*Vu[0,:] # Add to first cell
        rese[0,:] -= f[2]*Vu[0,:] # Add to first cell
        # Loop over internal faces
        # Left cell = i-1, right cell = i
        for i in range(1,nc):
            rhol = rho1[i-1,:].dot(Vu[-1,:])
            rhor = rho1[i  ,:].dot(Vu[ 0,:])
            moml = mom1[i-1,:].dot(Vu[-1,:])
            momr = mom1[i  ,:].dot(Vu[ 0,:])
            enel = ene1[i-1,:].dot(Vu[-1,:])
            ener = ene1[i  ,:].dot(Vu[ 0,:])
            f  = numflux([rhol,moml,enel], [rhor,momr,ener])
            resr[i-1,:] += f[0]*Vu[-1,:]
            resr[i  ,:] -= f[0]*Vu[ 0,:]
            resm[i-1,:] += f[1]*Vu[-1,:]
            resm[i  ,:] -= f[1]*Vu[ 0,:]
            rese[i-1,:] += f[2]*Vu[-1,:]
            rese[i  ,:] -= f[2]*Vu[ 0,:]
        # last face
        rhol = rho1[-1,:].dot(Vu[0,:])
        rhor = rho1[-1,:].dot(Vu[0,:])
        moml = mom1[-1,:].dot(Vu[0,:])
        momr = mom1[-1,:].dot(Vu[0,:])
        enel = ene1[-1,:].dot(Vu[0,:])
        ener = ene1[-1,:].dot(Vu[0,:])
        f  = numflux([rhol,moml,enel],[rhor,momr,ener])
        resr[-1,:] += f[0]*Vu[0,:] # Add to first cell
        resm[-1,:] += f[1]*Vu[0,:] # Add to first cell
        rese[-1,:] += f[2]*Vu[0,:] # Add to first cell
        # Peform rk stage
        rho1[:,:] = ark[rk]*rho0 + brk[rk]*(rho1 - lam*resr)
        mom1[:,:] = ark[rk]*mom0 + brk[rk]*(mom1 - lam*resm)
        ene1[:,:] = ark[rk]*ene0 + brk[rk]*(ene1 - lam*rese)
    t += dt; it += 1
    if it%args.plot_freq == 0 or np.abs(Tf-t) < 1.0e-13:
        update_plot(lines,t,rho1)

plt.show() # Dont close window at end of program
