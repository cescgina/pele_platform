import os
from AdaptivePELE.freeEnergies import extractCoords, prepareMSMFolders, estimateDGAdaptive
import MSM_PELE.Helpers.helpers as hp
import shutil

# DEFAULT VALUES
LAGTIME = 100
NCLUSTER = 200
CLUSTERINSTRIDE = 10


def analyse_results(output_pele, ligand_resname, cpus, pele_dir, atom_ids=""):
    trajs_per_epoch = cpus
    with hp.cd(output_pele):
        extractCoords.main(lig_resname=ligand_resname, non_Repeat=True, atom_Ids=atom_ids)
        prepareMSMFolders.main()
        estimateDGAdaptive.main(trajs_per_epoch, LAGTIME, NCLUSTER, CLUSTERINSTRIDE)
        results_file = summerize(output_pele)
        shutil.move(results_file, pele_dir)

def summerize(pele_path):
    results_file = os.path.join(pele_path, "results.txt")
    with open(results_file, 'r') as results:
        lines = hp.preproces_lines(results.readlines())
        for i, line in enumerate(lines):
            try:
                _, dg, stdDg, _, _ = line
                convergence = asses_convergence(dg, stdDg)
            except ValueError:
                pass
            else:
                line.append(convergence)
            finally:
                lines[i] = " ".join(line)
    with open(results_file, 'w') as results:
        results.write("\n".join(lines)+"\n")
	return results_file

def asses_convergence(dg, stdDg):
    """
       Asses whether the MSM analysis
           was good (G), medium (M) or bad (B).
    """
    convergence = "M"
    convergence_rate = round((abs(float(stdDg)*100)/float(dg)))
    if(convergence_rate < 5):
        convergence = "G"
    elif(convergence_rate > 10):
        convergence = "B"
    return convergence


if __name__ == "__main__":
        analyse_results("/home/dsoler/STR_PEle/output_pele", "STR")
