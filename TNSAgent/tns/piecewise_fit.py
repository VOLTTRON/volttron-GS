#python function translation of the matlab PiecewiseLinear
#developed by Nick Fernandez at PNNL
#this function imports the capacity and efficiency points for
#a microgrid component in question and outputs piecewise fit
#coefficients for linear curves
#INPUTS:
#comp_name: name of the file associated with component data
#capacity: max output of component (fraction)
#efficiency: powerout/powerin (fraction)
#regression_order: what order regression fit
#max_cap: maximum output of component capacity
#OUTPUTS:
#coeffarray0: 0th order coefficients (constants, b part of ax+b)
#coeffarray1: 1st order coefficients (linear, a part of ax+b)
#xmin: lower bound on segment
#xmax: upper bound on segment

import os
import numpy as np

def bin_data(capacity, efficiency, temperature, n_bins = 3):
    # this function bins the capacity and efficiency data by temperature to facilitate
    # creating higher accuracy piecwise fitcurves when the temperature is known
    # INPUTS:
    # - capacity: array of normalized capacity sample data
    # - efficiency: array of efficiency sample data
    # - temperature: array of temperature readings in degrees C
    # - n_bins: integer value for number of bins to separate data into
    # OUTPUTS:
    # - cap_binned: list of capacity data separated into arrays corresponding with the temperature bins
    # - eff_binned: list of efficiency data separated into arrays corresponding with the temperature bins
    # - temp_min: list of minimum temperatures for each bin
    # - temp_max: list of maximum temperatures for each bin, temp_min = [0, temp_max[:-1]]

    
    return cap_binned, eff_binned, temp_min, temp_max

def piecewise_linear(capacity, efficiency, regression_order=4, resolution=20, error_thresh=0.05, max_cap=1):
    capacity = max_cap*capacity[efficiency!=0]
    efficiency = 1/efficiency[efficiency!=0]*capacity
    error_thresh = error_thresh*max_cap
    #find high dimensional polyfit
    regression_coefs = np.flip(np.polyfit(capacity, efficiency, regression_order))

    #find linear regression for first section
    x0 = min(capacity)
    y0 = find_y(regression_coefs, x0)
    x1 = x0+(1/resolution)*(1-x0)
    y1 = find_y(regression_coefs, x1)
    coeff = np.polyfit([x0,x1], [y0, y1], 1)
    coeffarray0 = [coeff[0]]
    coeffarray1 = [coeff[1]]
    xmin = [x0]
    xmax = []
    xn = max(capacity)

    #find coefficients and min and max for each segment
    for i in range(1,resolution+1):
        xn = x0+(i/resolution)*(max_cap-x0)
        yn = find_y(regression_coefs, xn)
        yp = coeffarray1[-1] + coeffarray0[-1]*xn
        error = abs(yn-yp)
        #if the error gets too high, make a new segment
        if error>error_thresh:
            xn_1 = x0 + (i-1)/resolution*(max_cap-x0)
            yn_1 = find_y(regression_coefs, xn_1)
            coeff = np.polyfit([xn_1, xn], [yn_1, yn], 1)
            #make sure to get rid of rounding errors
            for c in range(2):
                if np.abs(coeff[c])<1e-3:
                    coeff[c] = 0
            coeffarray0.append(coeff[-1])
            coeffarray1.append(coeff[-2])
            xmin.append(xn_1)
            xmax.append(xn_1)
    xmax.append(xn)

    #refit each segment according to new thresholds
    for i in range(len(xmin)):
        x1 = xmin[i]
        x2 = xmax[i]
        y1 = find_y(regression_coefs, x1)
        y2 = find_y(regression_coefs, x2)
        coeff = np.polyfit([x1, x2], [y1, y2], 1)
        coeffarray0[i] = coeff[-1]
        coeffarray1[i] = coeff[-2]
    #prevent numerical issues by removing super small values
    coeffarray0 = np.array(coeffarray0)
    coeffarray1 = np.array(coeffarray1)
    coeffarray0[np.abs(coeffarray0)<1e-4] = 0.0
    coeffarray1[np.abs(coeffarray1)<1e-4] = 0.0

    return [np.array(coeffarray0), np.array(coeffarray1)], np.array(xmin), np.array(xmax)

############################################################################   
# this is based off of piecewise_linear which was
# originally created by Nick Fernandez at PNNL
# this function imports the capacity and efficiency points for
# a microgrid component in question and outputs a piecewise 
# quadratic fit of the cost curve ax**2 + bx + c
# INPUTS:
# comp_name: name of the file associated with component data
# capacity: max output of component
# regression_order: what order regression fit
# OUTPUTS:
# coeffarray0: 0th order coefficients (constants, c)
# coeffarray1: 1st order coefficients (linear, b)
# coeffarray2: 2nd order coefficients (quadratic, d)
def piecewise_quadratic(capacity, efficiency, regression_order=5, resolution=20, error_thresh=0.05, max_cap=1):
    #find high dimensional polyfit
    capacity = max_cap*capacity[efficiency!=0]
    efficiency = 1/efficiency[efficiency!=0]*capacity
    error_thresh = error_thresh*max_cap
    regression_coefs = np.flip(np.polyfit(capacity, efficiency, regression_order))
    #find quadratic fit for first section
    x0 = min(capacity)
    y0 = find_y(regression_coefs, x0)
    x1 = x0+(1/resolution)*(1-x0)
    y1 = find_y(regression_coefs, x1)
    xend = max(capacity)
    dx = (xend-x0)/resolution
    yend = find_y(regression_coefs, xend)
    coeff = np.flip(np.polyfit([x0,x1,xend], [y0,y1,yend], 2))
    coeffarray0 = [coeff[0]]
    coeffarray1 = [coeff[1]]
    coeffarray2 = [coeff[2]]
    if coeff[2]<0:
        coeff = np.flip(np.polyfit([x0,x1,xend], [y0,y1,yend], 1))
        coeffarray0[0] = coeff[0]
        coeffarray1[0] = coeff[1]
        coeffarray2[0] = 0.0
    xmin = [x0]
    xmax = []
    xn = max(capacity)

    #find coefficients and min and max for each segment
    for i in range(1,resolution+1):
        xn = x0+(i/resolution)*(max_cap-x0)
        yn = find_y(regression_coefs, xn)
        yp = coeffarray0[-1] + coeffarray1[-1]*xn + coeffarray2[-1]*xn**2
        error = abs(yn-yp)
        #if the error gets too high, make a new segment
        if error>error_thresh and i>1:
            xn_1 = x0 + (i-1)/resolution*(max_cap-x0)
            yn_1 = find_y(regression_coefs, xn_1)
            xn_2 = xn + dx
            yn_2 = find_y(regression_coefs, xn_2)
            coeff = np.polyfit([xn_1, xn, xn_2], [yn_1, yn, yn_2], 2)
            coeffarray0.append(coeff[-1])
            coeffarray1.append(coeff[-2])
            coeffarray2.append(coeff[-3])
            xmin.append(xn_1)
            xmax.append(xn_1)
    xmax.append(xn)

    #refit each segment according to new thresholds
    for i in range(len(xmin)):
        x1 = xmin[i]
        x2 = xmax[i]
        x_seg = [x1+j*dx for j in range(resolution) if x1+j*dx<x2]
        x_seg.append(x2)
        y_seg = [find_y(regression_coefs,x_seg_i) for x_seg_i in x_seg]
        coeff = np.polyfit(x_seg, y_seg, 2)
        coeffarray0[i] = coeff[-1]
        coeffarray1[i] = coeff[-2]
        coeffarray2[i] = coeff[-3]
        if coeff[-3]<0:
            coeff = np.polyfit(x_seg, y_seg, 1)
            coeffarray0[i] = coeff[-1]
            coeffarray1[i] = coeff[-2]
            coeffarray2[i] = 0.0
    #make sure you don't have numerical issues by preventing extremely small fit curve falues
    coeffarray0 = np.array(coeffarray0)
    coeffarray1 = np.array(coeffarray1)
    coeffarray2 = np.array(coeffarray2)
    coeffarray0[np.abs(coeffarray0)<1e-4] = 0.0
    coeffarray1[np.abs(coeffarray1)<1e-4] = 0.0
    coeffarray2[np.abs(coeffarray2)<1e-4] = 0.0

    return [np.array(coeffarray0), np.array(coeffarray1), np.array(coeffarray2)], np.array(xmin), np.array(xmax)
    

def find_y(coefs, x):
    y = 0
    for i in range(len(coefs)):
        y = y+coefs[i]*x**(i)
    return y



