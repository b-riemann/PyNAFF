from __future__ import absolute_import, division, print_function, unicode_literals
try:
    from builtins import range, int
except ImportError:
    from __builtin__ import range, int
import numpy as np
"""
# NAFF - Numerical Analysis of Fundamental Frequencies
# Version : 1.1.2
# Authors : F. Asvesta, N. Karastathis, P.Zisopoulos
# Contact : nkarast .at. cern .dot. ch
#
#
#	CHANGELOG
#	v0.1: Basic structure of code - NK
#	v1.0: Vectorizing computations & error catcher at modfre - NK FA
#	v1.1: Py3 compatibility - NK
"""

__version   = '1.1.2'
__PyVersion = [2.7, 3.6]
__authors   = ['F. Asvesta','N. Karastathis', 'P. Zisopoulos']
__contact   = ['nkarast .at. cern .dot. ch']


def naff(data, turns=300, nterms=1, skipTurns=0, getFullSpectrum=False):
	'''
	The function for NAFF
	Inputs :
			data 			= numpy array with TbT data
			turns 			= how many turns to get out of the data array
			nterms			= up to how many terms to look for (if less than this available execution will stop)
			skipTurns		= how many turns to skip from the input array
			getFullSpectrum = True  -> FFT : both negative and positive frequencies
					  False -> RFFT: only positive frequencies (abs)
	Returns : Array with frequencies and amplitudes in the format:
				[order of harmonic, frequency, Amplitude, Re{Amplitude}, Im{Amplitude}]
	'''
	if turns >= len(data)+1:
		raise ValueError('#naff : Input data must be at least of length turns+1.')
	if turns < 6:
		raise ValueError('#naff : Minimum number of turns is 6.')

	if np.mod(turns,6)!=0:
		a,b=divmod(turns,6)
		turns = int(6*a)

	NFR  = 100
	vars = {
	'NFS' 		: 0,
	'TFS' 		: np.zeros(NFR).astype('float64'),
	'ZAMP' 		: np.zeros(NFR).astype('complex128'),
	'ZALP'	 	: np.zeros((NFR,NFR)).astype('complex128'),
	'ZTABS' 	: np.array([]).astype('complex128'),
	'TWIN'  	: np.array([]).astype('float64'),
	}
	# - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - -
	def getIntegral(FR, turns):
		'''
		Calculate the integral using Hardy's method'
		'''
		if np.mod(turns, 6)!= 0:
			raise ValueError("Turns need to be *6")
		K = int(turns/6)

		i_line = np.linspace(1, turns, num=turns, endpoint=True)
		ZTF_tmp = vars['ZTABS'][1:]*vars['TWIN'][1:]*np.exp(-2.0*(i_line)*np.pi*1.0j*FR)
		ZTF = np.array(vars['ZTABS'][0]*vars['TWIN'][0])
		ZTF = np.append(ZTF, ZTF_tmp).ravel()
		N = turns + 1
		ZOM = 41.*ZTF[0]+216.*ZTF[1]+27.*ZTF[2]+272.*ZTF[3]+27.*ZTF[4]+216.*ZTF[5]+41.*ZTF[int(N)-1]
		for I in range(1, K):
			ZOM=ZOM+82.0*ZTF[6*I+1-1]+216.0*ZTF[6*I+2-1]+27.0*ZTF[6*I+3-1]+272.0*ZTF[6*I+4-1]+27.0*ZTF[6*I+5-1]+216.0*ZTF[6*I+6-1]
		ZOM=ZOM*(1.0/turns)*(6.0/840.0)
		A = np.real(ZOM)
		B = np.imag(ZOM)
		RMD = np.abs(ZOM)
		return RMD, A, B
	# - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - -
	def frefin(turns, FR, STAREP, EPS):
		'''
		Try to refine the frequency found using slopes & root finding methods
		'''
		EPSI = 1.0e-15
		X2  = FR
		PAS = STAREP
		Y2, A2, B2  = getIntegral(X2, turns)
		X1  = X2 - PAS
		X3  = X2 + PAS
		Y1, A1, B1  = getIntegral(X1, turns)
		Y3, A3, B3  = getIntegral(X3, turns)
		while True:
			if PAS >=EPS:
				if np.abs(Y3-Y1) < EPSI:
					break
				if (Y1<Y2) and (Y3<Y2):
					R2  = (Y1-Y2)/(X1-X2)
					R3  = (Y1-Y3)/(X1-X3)
					A   = (R2 - R3)/(X2-X3)
					B   = R2 - A*(X1+X2)
					XX2 = -B/(2.0*A)
					PAS = np.abs(XX2-X2)
					if XX2 > X2:
						X1 = X2
						Y1, A1, B1 = Y2, A2, B2
						X2 = XX2
						Y2, A2, B2 = getIntegral(X2, turns)
						X3 = X2 + PAS
						Y3, A3, B3 = getIntegral(X3, turns)
					else:
						X3 = X2
						Y3, A3, B3 = Y2, A2, B2
						X2 = XX2
						Y2, A2, B2 = getIntegral(X2, turns)
						X1 = X2 - PAS
						Y1, A1, B1 = getIntegral(X1, turns)
				else:
					if Y1>Y3:
						X2 = X1
						Y2, A2, B2 = Y1, A1, B1
					else:
						X2 = X3
						Y2, A2, B2 = Y3, A3, B3

					X1 = X2 - PAS
					X3 = X2 + PAS
					Y1, A1, B1 = getIntegral(X1, turns)
					Y3, A2, B2 = getIntegral(X3, turns)
					if (Y3-Y1)-(Y3-Y2)==0.0:
						PAS=PAS+EPS

			else:
				break
		return X2, Y2, A2, B2
	# - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - -
	def fretes(FR, FREFON):
		'''
		If more than one term found, check how different they are
		'''
		TOL   = 1.0e-4 # this is defined in mftnaf in lashkar
		IFLAG = 1
		NUMFR = 0
		ECART = np.abs(FREFON)
		for i in range(len(vars['TFS'])):
			TEST = np.abs(vars['TFS'][i] - FR)
			if TEST < ECART:
				if np.float(TEST)/np.float(ECART) < TOL:
					IFLAG = -1
					NUMFR = i
					break
				else:
					IFLAG = 0
					continue
		return IFLAG, NUMFR
	# - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - -
	def modfre(turns, FR, NUMFR, A, B):
		'''
		If I found something very close to one of the FR before, I assume that this comes from data
		I had not removed successfully => Remove them without orthonormalization
		'''
		ZI  = 0. + 1.0j
		ZOM = 1.0j*FR
		ZA  = 1.0*A + 1.0j*B
		if len(vars['ZAMP'])<= NUMFR:
			vars['ZAMP'][NUMFR] = 0
		vars['ZAMP'][NUMFR] = vars['ZAMP'][NUMFR] + ZA
		i_line = np.linspace(1, turns, num=turns, endpoint=True)
		ZT_tmp = ZA*np.exp(2.0*(i_line)*np.pi*ZOM)
		ZT     = np.array([ZA])
		ZT     = np.append(ZT, ZT_tmp).ravel()
		ZTABS_tmp = vars['ZTABS'] - ZT
		vars['ZTABS'] = ZTABS_tmp
	# - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - -
	def proscaa(turns, FS, FS_OLD):
		ZI = 0.0+1.0j
		OM = FS-FS_OLD
		ANGI = 2.0*np.pi*OM
		i_line = np.linspace(1, turns, num=turns, endpoint=True)
		ZT_tmp = np.exp(-2.0*(i_line)*1.0j*np.pi*OM)
		ZT_zero = np.array([1])
		ZT = np.append(ZT_zero, ZT_tmp).ravel()
		ZTF = np.multiply(vars['TWIN'],ZT)
		N = turns + 1
		ZOM = 41.*ZTF[0]+216.*ZTF[1]+27.*ZTF[2]+272.*ZTF[3]+27.*ZTF[4]+216.*ZTF[5]+41.*ZTF[int(N)-1]
		for I in range(1, int(turns/6)):
			ZOM=ZOM+82.0*ZTF[6*I+1-1]+216.0*ZTF[6*I+2-1]+27.0*ZTF[6*I+3-1]+272.0*ZTF[6*I+4-1]+27.0*ZTF[6*I+5-1]+216.0*ZTF[6*I+6-1]

		ZOM=ZOM*(1.0/turns)*(6.0/840.0)
		return ZOM
	# - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - -
	def gramsc(turns, FR, A, B):
		'''
		Remove the contribution of the frequency found from the Data and orthonormalize
		'''
		# global NFS
		# global ZTABS
		# global ZALP
		# global TFS
		# global ZAMP

		ZTEE = np.zeros(vars['NFS']+1).astype('complex128')
		for i in range(0, vars['NFS']):
			ZTEE[i] = proscaa(turns, FR, vars['TFS'][i])
		NF = vars['NFS']+1
		ZTEE[NF-1] = 1.0+0.0j
		vars['TFS'][NF-1] = FR
		for k in range(1,vars['NFS']+1):
			for i in range(1, vars['NFS']+1):
				for j in range(1,i+1):
					vars['ZALP'][NF-1, k-1] = vars['ZALP'][NF-1, k-1] - np.conj(vars['ZALP'][i-1,j-1])*vars['ZALP'][i-1,k-1]*ZTEE[j-1]

		vars['ZALP'][NF-1, NF-1] = 1.0+0.0j
		DIV  = 1.0
		ZDIV = 0.0+0.0j
		for i in range(0, NF):
			ZDIV = ZDIV + np.conj(vars['ZALP'][NF-1, i])*ZTEE[i]
		DIV = np.sqrt(np.abs(ZDIV))
		vars['ZALP'][NF-1,:] = vars['ZALP'][NF-1,:]/DIV
		ZMUL = np.complex(A,B)/DIV
		ZI = 0.0+1.0j

		for i in range(0, NF):
			ZOM = 1.0j*vars['TFS'][i]
			ZA  = vars['ZALP'][NF-1,i]*ZMUL
			vars['ZAMP'][i] = vars['ZAMP'][i]+ZA
			ZT_zero = np.array([ZA])
			i_line = np.linspace(1, turns, num=turns, endpoint=True)
			ZT_tmp = ZA*np.exp(2.0*(i_line)*1.0j*np.pi*vars['TFS'][i])
			ZT = np.append(ZT_zero, ZT_tmp).ravel()
			vars['ZTABS'] = vars['ZTABS'] - ZT


	# - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - - * - -
	FREFON = 1.0/turns
	NEPS   = 100000000
	EPS    = FREFON/NEPS

	T    = np.linspace(0, turns, num=turns+1, endpoint=True)*2.0*np.pi - np.pi*turns
	vars['TWIN'] = 1.0+np.cos(T/turns)
	vars['ZTABS'] = data[skipTurns:skipTurns+turns+1]

	TOL = 1.0e-4
	STAREP = FREFON/3.0
	for term in range(nterms):
		data_for_fft = np.multiply(vars['ZTABS'], vars['TWIN'])[:-1] # .astype('complex128')
		if getFullSpectrum:
			y = np.fft.fft(data_for_fft)
		else:
			y = np.fft.rfft(data_for_fft.astype('float64'))

		RTAB = np.sqrt(np.real(y)**2 + np.imag(y)**2)/turns  # normalized
		INDX = np.argmax(RTAB)
		VMAX = np.max(RTAB)

		if INDX == 0 :
			print('## PyNAFF: REMOVE DC FREQUENCY FROM DATA')
		if INDX <= turns/2.0:
			IFR = INDX - 1
		else:
			IFR = INDX-1-turns

		FR = (IFR+1)*FREFON
		FR, RMD, A, B = frefin(turns, FR, STAREP, EPS)
		IFLAG, NUMFR = fretes(FR, FREFON)
		if IFLAG ==1:
			gramsc(turns, FR, A, B)
			vars['NFS'] = vars['NFS'] + 1
		elif IFLAG == 0:
			# continue
			break  # if I put continue it will find again and again the same freq/ with break it stops repeating
		elif IFLAG == -1:
			modfre(turns, FR, NUMFR, A, B)

	result = []
	for i in range(vars['NFS']):
		AMP = np.abs(vars['ZAMP'][i])
		result.append(np.array([int(i), vars['TFS'][i], AMP, np.real(vars['ZAMP'][i]), np.imag(vars['ZAMP'][i])]))
	return np.array(result)


### - - - ### - - - ### - - - ### - - - ### - - - ### - - - ### - - - ### - - - ### - - - ### - - - ###

# Example
if __name__ == '__main__':
	x = np.linspace(1, 500, num=500, endpoint=True)
	data = np.sin(2.0*np.pi*0.34*x)+np.sin(2.0*np.pi*0.36*x)
	a = naff(data, 300, 20, 0, False)
	print(a)