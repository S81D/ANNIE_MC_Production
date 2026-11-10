import sys

# this script will execute on the grid
# it is used to populate the TreeMaker + LoadWCSim with the correct file names

run = sys.argv[1]

def LoadWCSim(run):

    file = open('LoadWCSimConfig', "w")

    file.write("verbose 1\n")
    file.write("InputFile wcsim_" + run + ".root\n")
    file.write("\n")
    file.write("WCSimVersion 3\n")
    file.write("HistoricTriggeroffset 0\n")
    file.write("UseDigitSmearedTime 0\n")
    file.write("LappdNumStrips 56\n")
    file.write("LappdStripLength 100\n")
    file.write("LappdStripSeparation 10\n")
    file.write("PMTMask ./configfiles/LoadWCSim/DeadPMTIDs_p2v7.txt\n")
    file.write("ChankeyToPMTIDMap ./configfiles/LoadWCSim/Chankey_WCSimID_v7.txt\n")
    file.write("ChankeyToMRDIDMap ./configfiles/LoadWCSim/MRD_Chankey_WCSimID.dat\n")
    file.write("ChankeyToFMVIDMap ./configfiles/LoadWCSim/FMV_Chankey_WCSimID.dat\n")

    file.close()

    return


def PhaseIITreeMaker():

    file = open('PhaseIITreeMakerConfig', "w")

    file.write('verbose 0\n')
    file.write('OutputFile tree.root\n')
    file.write('TankClusterProcessing 1\n')
    file.write('MRDClusterProcessing 1\n')
    file.write('TriggerProcessing 1\n')
    file.write('TankHitInfo_fill 1\n')
    file.write('MRDHitInfo_fill 1\n')
    file.write('MRDReco_fill 1\n')
    file.write('SiPMPulseInfo_fill 0\n')
    file.write('fillCleanEventsOnly 0\n')
    file.write('MCTruth_fill 1\n')
    file.write('Reco_fill 1\n')
    file.write('TankReco_fill 0\n')
    file.write('RecoDebug_fill 0\n')
    file.write('muonTruthRecoDiff_fill 0\n')
    file.write('IsData 0\n')
    file.write('PMTWaveformSim 1\n')
    file.write('HasBNBtimingMC 1\n')
    file.write('HasGenie 1\n')
    file.write('VertexLeastSquares 1')

    file.close()

    return

# For WORLD samples, your LoadGENIEEventConfig should look like this:
'''
verbosity 0
FluxVersion 1
FileDir .
FilePattern LoadWCSimTool
ManualFileMatching 0
FileEvents 1000
EventOffset 0
'''
# It will interpret the name from the LoadWCSim tool, and since its being run on the grid, your FileDir is: '.'


def main(run):

    LoadWCSim(run)
    PhaseIITreeMaker()

    return

main(run)
