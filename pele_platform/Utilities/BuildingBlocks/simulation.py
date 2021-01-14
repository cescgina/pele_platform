from dataclasses import dataclass
import glob
import os

import pele_platform.Adaptive.simulation as si
import pele_platform.Errors.custom_errors as ce
from pele_platform.Utilities.Helpers.helpers import retrieve_box
from pele_platform.Utilities.BuildingBlocks.preparation import prepare_structure
import pele_platform.Utilities.Parameters.pele_env as pv
import pele_platform.features.adaptive as ft

@dataclass
class Simulation:
    """
    Base Simulation class to run all simulation types.
    Both input and output should always be EnviroBuilder.

    One class to rule them all, one class to find them, one class to bring them all and in PELE bind them.
    """
    env: pv.EnviroBuilder
    options: dict

    def run_simulation(self, keyword, folder_name):
        self.keyword = keyword
        self.set_params(simulation_type=keyword)
        self.set_working_folder(folder_name)
        self.env.build_adaptive_variables(self.env.initial_args)
        self.set_user_params()
        self.create_folders()
        if hasattr(self.env, "next_step"):
            self.env.input = glob.glob(self.env.next_step)
        if self.env.initial_args.ppi is True and keyword == "induced_fit_exhaustive":  # I don't really like this, any ideas?
            self.env.system = prepare_structure(self.env.system, self.env.ligand_pdb, self.env.protein, remove_water=False)
        
        self.restart_checker()
        self.water_handler()

        # check for special params
        if self.keyword == "gpcr_orth":
            self.set_gpcr_params()
        elif self.keyword == "out_in":
            self.set_outin_params()

        self.env = si.run_adaptive(self.env)
        return self.env

    def restart_checker(self):
        """
        Check if we should run restart based on the presence of the output folder and 'adaptive_restart' flag in
        input.yaml.
        """
        output_dir = os.path.join(self.env.pele_dir, self.env.output)
        if self.env.adaptive_restart and os.path.exists(output_dir):
            self.env.adaptive_restart = True
        else:
            self.env.adaptive_restart = False

    def set_params(self, simulation_type):
        """
        Make sure all simulations are set to False, then set the one you need to True. This is to avoid scenarios where
        we have induced_fit_fast: true and rescoring: true, because some random parameters were carried over.
        """
        for sim in ft.all_simulations:  # make sure everything else is False
            setattr(self.env, sim, False)
        setattr(self.env, simulation_type, True)  # set the simulation you need

    def set_user_params(self):
        """
        Overriding default pele_env variables by user-defined parameters from input.yaml.
        """
        if self.options:
            for key, value in self.options.items():
                setattr(self.env, key, value)

    def set_working_folder(self, folder_name):
        self.original_dir = os.path.abspath(os.getcwd())
        
        # Check if user specified a custom folder name for this simulation block. If not, use the automatically generated one.
        if self.options:
            user_folder = self.options.get("working_folder", None)
            self.env.folder_name = user_folder if user_folder else folder_name
        else:
            self.env.folder_name = folder_name

        if hasattr(self.env, "pele_dir"):
            self.env.initial_args.folder = os.path.join(os.path.dirname(self.env.pele_dir), self.env.folder_name)

    def create_folders(self):
        self.env.create_files_and_folders()

    def water_handler(self):
        """
        In the PPI package, water perturbation is only executed in the refinement simulation.
        """
        if self.env.package == "ppi" and hasattr(self.env.initial_args, "n_waters"):
            if self.keyword == "induced_fit_exhaustive":
                self.env._n_waters = self.env.n_waters
                self.env.n_waters = 0
                self.env.water_arg = None
            else:
                if self.env._n_waters !=0:
                    self.env.waters = "all_waters"
                    self.env.n_waters = n_waters
                else:
                    self.env.waters = None
                    self.env.n_waters = self.env._n_waters


@dataclass
class GlobalExploration(Simulation):

    env: pv.EnviroBuilder
    options: dict
    folder_name: str

    def run(self):
        self.env = self.run_simulation("full", self.folder_name)
        return self.env


@dataclass
class InducedFitFast(Simulation):

    env: pv.EnviroBuilder
    options: dict
    folder_name: str

    def run(self):
        self.env = self.run_simulation("induced_fit_fast", self.folder_name)
        return self.env


@dataclass
class InducedFitExhaustive(Simulation):

    env: pv.EnviroBuilder
    options: dict
    folder_name: str

    def run(self):
        if self.env.package == "ppi":
            self.env.water_arg = None
        self.env = self.run_simulation("induced_fit_exhaustive", self.folder_name)
        return self.env


@dataclass
class Rescoring(Simulation):

    env: pv.EnviroBuilder
    options: dict
    folder_name: str

    def run(self):
        if self.env.package == "ppi":
            self.set_ppi_params()
        self.env = self.run_simulation("rescoring", self.folder_name)
        return self.env

    def set_ppi_params(self):
        """
        Overrides default Rescoring parameters if running PPI.
        """
        if not self.env.test:
            self.env.iterations = 1
            self.env.steps = 100
            self.env.box_radius = 100

        if self.env._n_waters:
            self.env.n_waters = self.env._n_waters


@dataclass
class GPCR(Simulation):
    env: pv.EnviroBuilder
    options: dict
    folder_name: str

    def run(self):
        self.env = self.run_simulation("gpcr_orth", self.folder_name)
        return self.env

    def set_gpcr_params(self):
        self.env.orthosteric_site = self.env.initial_args.orthosteric_site
        self.env.initial_site = self.env.initial_args.initial_site
        self.env.center_of_interface = self.env.initial_site
        box_center, box_radius = retrieve_box(self.env.system, self.env.initial_site, self.env.orthosteric_site,
                                              weights=[0.35, 0.65])
        self.env.box_center = self.env.initial_args.box_center if self.env.initial_args.box_center else box_center
        self.env.box_radius = self.env.initial_args.box_radius if self.env.initial_args.box_radius else box_radius
        self.env.randomize = True


@dataclass
class Selection:

    simulation_params: pv.EnviroBuilder
    folder: str

    def run(self):
        self.choose_refinement_input()
        return self.simulation_params

    def choose_refinement_input(self):
        """
        Choose input for refinement simulation.
        Scan top 75% binding energies, pick n best ones as long as ligand COMs are >= 6 A away from each other.
        """
        simulation_path = os.path.join(self.simulation_params.pele_dir, self.simulation_params.output)
        n_best_poses = int(self.simulation_params.iterations * self.simulation_params.pele_steps * (
                self.simulation_params.cpus - 1) * 0.75)
        with cd(simulation_path):
            files_out, _, _, _, output_energy = bs.main(str(self.simulation_params.be_column), n_structs=n_best_poses,
                                                        path=".",
                                                        topology=self.simulation_params.topology,
                                                        logger=self.simulation_params.logger)

            snapshot = 0
            files_out = [os.path.join(self.simulation_params.pele_dir, "results", f) for f in files_out]
            input_pool = [[f, snapshot, self.simulation_params.residue, self.simulation_params.topology] for f in
                          files_out]
            all_coords = parallelize(_extract_coords, input_pool, self.simulation_params.cpus)
            coords = [list(c[0:3]) for c in all_coords]
            dataframe = pd.DataFrame(list(zip(files_out, output_energy, coords)),
                                     columns=["File", "Binding energy", "1st atom coordinates"])
            dataframe = dataframe.sort_values(["Binding energy"], ascending=True)

            inputs = self._check_ligand_distances(dataframe)
            directory = os.path.join(os.path.dirname(self.simulation_params.pele_dir),
                                     self.folder)
            if not os.path.isdir(directory):
                os.makedirs(directory, exist_ok=True)
            for i in inputs:
                os.system("cp {} {}/.".format(i, directory))

            self.simulation_params.next_step = os.path.join(directory, "*.pdb")

    def _check_ligand_distances(self, dataframe):

        inputs = []
        input_coords = []
        distances = []
        n_inputs = self.simulation_params.cpus - 1
        
        while len(inputs) < n_inputs:
            for f, c in zip(dataframe['File'], dataframe['1st atom coordinates']):
                if not input_coords:
                    inputs.append(f)
                    input_coords.append(c)
                else:
                    for ic in input_coords:
                        distances.append(abs(np.linalg.norm(np.array(c) - np.array(ic))))
                    distances_bool = [d > 6 for d in distances]
                    if all(distances_bool):
                        inputs.append(f)
                        input_coords.append(c)
            break  # make sure it stops after running out of files to check
        
        return inputs


@dataclass
class Pipeline:
    iterable: list
    env: pv.EnviroBuilder

    def run(self):
        output = []
        for simulation in self.iterable:
            folder = "{}_{}".format(self.iterable.index(simulation) + 1, simulation.__name__)
            self.env = simulation(self.env, folder).run()
            output.append(deepcopy(self.env))

        return output

class OutIn(Simulation):
    env: pv.EnviroBuilder
    options: dict
    folder_name: str

    def run(self):
        self._check_mandatory_fields()
        self.env = self.run_simulation("out_in", self.folder_name)
        return self.env

    def _check_mandatory_fields(self):
        compulsory_flags = ["final_site", "initial_site"]
        for flag in compulsory_flags:
            if getattr(self.env.initial_args, flag) is None:
                raise ce.OutInError(f"Flag {flag} must be specified for out_in package.")

    def set_outin_params(self):
        self.env.final_site = self.env.initial_args.final_site
        self.env.initial_site = self.env.initial_args.initial_site
        self.env.center_of_interface = self.env.initial_site
        box_center, box_radius = retrieve_box(
            self.env.initial_args.system, self.env.initial_site, self.env.final_site,
            weights=[0.35, 0.65])
        self.env.box_center = self.env.initial_args.box_center if self.env.initial_args.box_center else box_center
        self.env.box_radius = self.env.initial_args.box_radius if self.env.initial_args.box_radius else box_radius
        self.env.randomize = True