import os
import glob
import pandas as pd
import pytest
import shutil

import pele_platform.constants.constants as cs
import pele_platform.main as main
from pele_platform.analysis import Analysis, DataHandler, Plotter
from pele_platform.Utilities.Helpers.helpers import check_remove_folder


test_path = os.path.join(cs.DIR, "Examples")
simulation_path = "../pele_platform/Examples/analysis/data/output"
REPORT_NAME = "report"
TRAJ_NAME = "trajectory.pdb"

ANALYSIS_ARGS = os.path.join(test_path, "analysis/input.yaml")
ANALYSIS_FLAGS0 = os.path.join(test_path, "analysis/input_flags0.yaml")
ANALYSIS_FLAGS = os.path.join(test_path, "analysis/input_flags.yaml")
ANALYSIS_XTC_ARGS = os.path.join(test_path, "analysis/input_xtc.yaml")

expected_energies = [
    -8699.17,
    -8690.68,
    -8711.55,
    -8709.73,
    -8687.3,
    -8706.14,
    -8712.07,
]


@pytest.mark.parametrize(("x", "y", "z"), [(4, 5, 6), (5, 6, None)])
def test_plotter(x, y, z):
    """
    Checks if the scatter and KDE plots are created correctly.

    Parameters
    ----------
    x : int
        Metric to x
    y :
        Metric to y
    z :
        Metric to z
    """
    output_folder = "tmp/plots"
    check_remove_folder(output_folder)

    data_handler = DataHandler(
        sim_path=simulation_path,
        report_name=REPORT_NAME,
        trajectory_name=TRAJ_NAME,
        be_column=5,
    )
    dataframe = data_handler.get_reports_dataframe()
    plotter = Plotter(dataframe)
    output_scatter = plotter.plot_two_metrics(x, y, z, output_folder=output_folder)
    output_kde = plotter.plot_kde(x, y, output_folder=output_folder, kde_structs=10)

    assert os.path.exists(output_scatter)
    assert os.path.exists(output_kde)


@pytest.mark.parametrize(
    ("n_poses", "expected_energies"),
    [
        (0, []),
        (1, [0.879]),
        (4, [0.879, 2.203, 3.563, 6.624]),
    ],
)
def test_generate_top_poses(analysis, n_poses, expected_energies):
    """
    Checks if data_handler extracts the correct number of top poses and associated metrics.
    """
    output_folder = "tmp/top_poses"
    check_remove_folder(output_folder)

    top_poses = analysis.generate_top_poses(output_folder, n_poses)
    top_poses_rounded = [round(pose, 3) for pose in top_poses]

    # Check if correct energy values were extracted
    assert len(top_poses) == n_poses
    for energy in expected_energies:
        assert energy in top_poses_rounded

    # Check if correct number of files was saved
    results = [
        os.path.basename(file)
        for file in glob.glob(os.path.join(output_folder, "*pdb"))
    ]
    assert len(results) == n_poses


@pytest.mark.parametrize(
    ("yaml_file", "n_expected_outputs", "expected_files"),
    [
        (
            ANALYSIS_FLAGS0,
            4,
            [
                "distance0_Binding_Energy_plot.png",
                "currentEnergy_Binding_Energy_distance0_plot.png",
                "sasaLig_Binding_Energy_plot.png",
                "currentEnergy_Binding_Energy_sasaLig_plot.png",
            ],
        ),
        (
            ANALYSIS_FLAGS,
            2,
            [
                "currentEnergy_Binding_Energy_distance0_plot.png",
                "distance0_Binding_Energy_plot.png",
            ],
        ),
    ],
)
def test_analysis_flags(yaml_file, n_expected_outputs, expected_files):
    """
    Runs full simulation with input.yaml with some unusual flags, check the number of top poses, created plots and their
    names to ensure correct metrics were take into account.

    Parameters
    ----------
    yaml_file : str
        Path to input.yaml
    n_expected_outputs : int
        Number of expected plots.
    expected_files : List[str]
        List of expected plot names.
    """
    output_folder = "../pele_platform/Examples/analysis/data/results"
    plots_folder = os.path.join(output_folder, "plots")
    top_poses_folder = os.path.join(output_folder, "top_poses", "*pdb")

    main.run_platform_from_yaml(yaml_file)

    # Check if all expected file names are present

    for file in expected_files:
        file_path = os.path.join(plots_folder, file)
        assert os.path.exists(file_path)

    # Check number of created plots and top poses
    all_plots = glob.glob(os.path.join(plots_folder, "*png"))
    assert len(all_plots) == n_expected_outputs

    all_top_poses = glob.glob(top_poses_folder)
    assert len(all_top_poses) == 0

    check_remove_folder(output_folder)


@pytest.mark.parametrize(
    ("yaml_file", "expected_poses", "expected_clusters"),
    [(ANALYSIS_ARGS, 1, 0), (ANALYSIS_XTC_ARGS, 3, 2)],
)
def test_analysis_production(yaml_file, expected_poses, expected_clusters):
    """
    Runs production analysis from input.yaml, both for PDB and XTC trajectories.

    Parameters
    ----------
    yaml_file : str
        Path to input.yaml
    """
    job_params = main.run_platform_from_yaml(yaml_file)

    results_folder = os.path.join(job_params.pele_dir, "results")
    top_poses = glob.glob(os.path.join(results_folder, "top_poses/*pdb"))
    clusters = glob.glob(os.path.join(results_folder, "clusters/*pdb"))
    params_file = os.path.join(results_folder, "parameters.txt")

    assert len(top_poses) == expected_poses
    assert len(clusters) == expected_clusters
    assert os.path.isfile(params_file)

    with open(params_file, "r") as file:
        content = file.read()
        assert "clustering_type: meanshift" in content

    # Clean up
    check_remove_folder(results_folder)


@pytest.mark.parametrize(
    ("method", "bandwidth", "n_clusters"),
    [
        ("hdbscan", 5, 0),  # only gets orphan clusters [-1]
        ("meanshift", 100, 1),
        ("meanshift", 30, 3),
        ("meanshift", "auto", 5),
        ("gaussianmixture", 1, 2),
    ],
)
def test_generate_clusters(analysis, method, bandwidth, n_clusters):
    """
    Checks if built-in clustering methods are producing expected number of clusters.

    Parameters
    ----------
    method : str
        Built-in clustering method, e.g. "dbscan".
    bandwidth : float
        Bandwidth for meanshift (or epsilon for DBSCAN).
    n_clusters : int
        Number of clusters for the Gaussian mixture model.
    """
    working_folder = "clustering_method"

    analysis.generate_clusters(
        working_folder, method, bandwidth=bandwidth, analysis_nclust=n_clusters
    )

    results = glob.glob(os.path.join(working_folder, "*pdb"))
    results = [element for element in results if "water" not in element]

    assert len(results) == n_clusters
    check_remove_folder(working_folder)


def test_api_analysis_generation(analysis):
    """
    Runs full analysis workflow (with GMM clustering).
    """
    working_folder = "full_analysis"
    check_remove_folder(working_folder)
    n_clusts = 3
    analysis.generate(working_folder, "gaussianmixture", analysis_nclust=n_clusts)

    # Check if reports exist
    assert os.path.exists(os.path.join(working_folder, "summary.pdf"))

    # Check plots
    plots = glob.glob(os.path.join(working_folder, "plots", "*png"))
    assert len(plots) == 2

    # Check top poses
    top_poses = glob.glob(os.path.join(working_folder, "top_poses", "*pdb"))
    assert len(top_poses) == 7

    # Check clusters
    clusters = glob.glob(os.path.join(working_folder, "clusters", "*pdb"))
    assert len(clusters) == 6  # includes water and ligand clusters, so n_clusts x 2

    # Check cluster representatives CSV by testing for the presence of columns from both trajectory and metrics dfs
    top_selections = os.path.join(working_folder, "clusters", "top_selections.csv")
    df = pd.read_csv(top_selections)
    assert all(
        [x in df.columns
         for x in [
             "Cluster label",
             "epoch",
             "trajectory",
             "Step",
             "currentEnergy",
             "Binding Energy",
             "sasaLig",
         ]]
    )

    # Check if data.csv exists and is not empty
    data_csv = os.path.join(working_folder, "data.csv")
    assert os.path.exists(data_csv)

    with open(data_csv, "r") as file:
        lines = file.readlines()
        assert len(lines) == 8
        assert (
            lines[0]
            == "Step,numberOfAcceptedPeleSteps,currentEnergy,Binding Energy,sasaLig,epoch,trajectory,"
            "Cluster\n"
        )

    check_remove_folder(working_folder)


def test_check_existing_directory(generate_folders):
    """
    Checks if tester of existing dir

    Parameters
    ----------
    generate_folders : pytest.fixture
        Pytest fixture that generates "results" folders for testing
    """
    new_path = Analysis._check_existing_directory("results")
    assert new_path == "results_3"

    folders = glob.glob("results*")
    check_remove_folder(*folders)


@pytest.mark.parametrize("max_coordinates", [1, 3])
def test_extract_and_filter_coordinates(analysis, max_coordinates):
    """
    Checks coordinates and dataframe extraction and its subsequent filtering.

    Parameters
    ----------
    analysis : Analysis
        Analysis object created in a fixture.
    max_coordinates : int
        Number of coordinates to extract per ligand.
    """
    coordinates, water_coordinates, dataframe = analysis._extract_coordinates(
        max_coordinates
    )
    coordinates_filtered, _, _, _ = analysis._filter_coordinates(
        coordinates, None, dataframe, 0.5
    )

    assert len(coordinates) == 7
    assert coordinates.shape == (
        7,
        max_coordinates,
        3,
    )  # 7 poses, n atoms, 3 coordinates

    assert len(dataframe) == 7
    assert dataframe["currentEnergy"].tolist().sort() == expected_energies.sort()
    assert len(coordinates_filtered) == 4


def test_extract_poses(analysis):
    """
    Tests poses extraction from dataframe.

    Parameters
    ----------
    analysis : Analysis object
        Created in analysis fixture.
    """

    output = "extracted_poses"
    check_remove_folder(output)

    values = analysis._extract_poses(analysis._dataframe, "currentEnergy", output)
    poses = glob.glob(os.path.join(output, "*pdb"))

    assert values.sort() == expected_energies.sort()
    assert len(poses) == 7

    check_remove_folder(output)


@pytest.mark.parametrize(
    ("filter", "threshold", "expected_length"), [(True, 0.5, 1), (False, None, 7)]
)
def test_get_dataframe(analysis, filter, threshold, expected_length):
    """
    Tests dataframe filtering based on highest energy. Filtering happens twice, for binding energy and total energy,
    therefore a threshold of 50% will only return one pose out of 7.

    Parameters
    ----------
    analysis : Analysis
        Analysis object created in a fixture.
    """

    df = analysis.get_dataframe(threshold=threshold)
    assert len(df) == expected_length


@pytest.mark.parametrize(
    ("cluster_selection", "expected_value"),
    [
        ("interaction_25_percentile", 0.879497),
        ("interaction_5_percentile", 0.879497),
        ("population", 0.2),
        ("interaction_mean", 0.879497),
    ],
)
def test_top_clusters_criterion_flag(analysis, cluster_selection, expected_value):
    """
    It tests the selection for the clustering method and checks whether the top cluster (A) has the expected top value,
    e.g. lowest mean binding energy.

    Parameters
    ----------
    analysis : Analysis object
        Created automatically by a fixture.
    cluster_selection : str
        Selection method, e.g. "rmsd", "population"... see parameters above.
    expected_value : float
        Metric value expected to be associated with the selected cluster A.
    """

    output_folder = "cluster_selection_test"
    csv = os.path.join(output_folder, "info.csv")

    analysis.generate_clusters(
        path=output_folder,
        clustering_type="meanshift",
        bandwidth=2.5,
        analysis_nclust=10,
        max_top_clusters=1,
        top_clusters_criterion=cluster_selection,
        min_population=0.01,
    )

    df = pd.read_csv(csv)
    clusterA_index = df.index[df["Selected labels"] == "A"]
    (top_value,) = (
        df[cs.metric_top_clusters_criterion[cluster_selection]]
        .iloc[clusterA_index]
        .tolist()
    )
    assert top_value == expected_value
    check_remove_folder(output_folder)


@pytest.mark.parametrize(
    ("criterion", "expected"),
    [
        ("interaction_5_percentile", ""),
        ("interaction_25_percentile", ""),
        ("interaction_mean", ""),
    ],
)
def test_cluster_representatives_criterion_flag(analysis, criterion, expected):
    """
    Tests the user-defined method of selecting cluster representatives.

    Parameters
    ----------
    analysis : Analysis object
        Created by a fixture.
    criterion : str
        cluster_representatives_criterion flag defined by the user.
    expected : str
        Expected value in the dataframe.
    TODO: Manually check expected values and then add them to the test to make sure we're getting the right stuff!
    """

    output_folder = "cluster_rep_selection"
    csv = os.path.join(output_folder, "top_selections.csv")

    analysis.generate_clusters(
        path=output_folder,
        clustering_type="meanshift",
        bandwidth=2.5,
        max_top_clusters=1,
        representatives_criterion=criterion,
    )

    df = pd.read_csv(csv)
    assert all(
        [x in df.columns
         for x in [
            "Cluster label",
            "epoch",
            "trajectory",
            "Step",
            "currentEnergy",
            "Binding Energy",
            "sasaLig",
         ]]
    )
    assert not df.isnull().values.any()

    check_remove_folder(output_folder)


def test_coordinates_extraction_from_trajectory():
    """
    Test extraction of water coordinates and clustering.
    """
    output = "../pele_platform/Examples/clustering"

    data_handler = DataHandler(
        sim_path=output,
        report_name=REPORT_NAME,
        trajectory_name=TRAJ_NAME,
        be_column=5,
        skip_initial_structures=False,
    )

    trajectory = glob.glob(os.path.join(output, "*", "trajectory*"))[0]
    residue, water = data_handler._get_coordinates_from_trajectory(
        "LIG",
        True,
        trajectory,
        only_first_model=False,
        water_ids=[("A", 2109), ("A", 2124)],
    )
    assert residue.shape == (2, 18, 3)
    assert water.shape == (2, 2, 3)


def get_analysis(output, topology, traj):
    """
    Calls analysis fixture with the right arguments depending on the trajectory type.

    Parameters
    -----------
    output : str
        Path to simulation 'output' folder.
    topology : str
        Path to the topology file.
    traj : str
        Trajectory type: xtc or pdb.
    """
    traj = traj if traj else "pdb"
    trajectory = f"trajectory.{traj}"
    analysis = Analysis(
        resname="LIG",
        chain="Z",
        simulation_output=output,
        skip_initial_structures=False,
        topology=topology,
        water_ids_to_track=[("A", 2109), ("A", 2124)],
        traj=trajectory,
    )
    return analysis


@pytest.mark.parametrize(
    ("path", "topology"),
    [
        (
            "../pele_platform/Examples/clustering_xtc",
            "../pele_platform/Examples/clustering_xtc/0/topology.pdb",
        ),
        ("../pele_platform/Examples/clustering", None),
    ],
)
def test_water_clustering(path, topology):
    """
    Tests full water clustering on both XTC and PDB trajectories.
    """
    traj = "xtc" if topology else "pdb"
    analysis_output = "water_clustering"

    obj = get_analysis(path, topology, traj)
    obj.generate_clusters(path=analysis_output, clustering_type="meanshift")
    # TODO: Write a proper test for water clustering output once it's implemented.

    check_remove_folder(analysis_output)


def test_water_clustering_production():
    """
    Tests water clustering running from YAML.
    """
    yaml = os.path.join(test_path, "clustering_xtc", "water_clustering.yaml")
    parameters = main.run_platform_from_yaml(yaml)

    # Checking if water indices to track are correctly parsed
    assert parameters.water_ids_to_track == [("A", 2334), ("A", 2451)]

    # TODO: Write a proper test for water clustering output once it's implemented.


def test_empty_reports_handling():
    """
    Checks if we handle reports with no accepted PELE steps to make sure the returned empty coordinates array doesn't
    cause any errors.
    """
    simulation_output = os.path.join(test_path, "analysis/data/empty_reports_output")
    analysis = Analysis(
        simulation_output=simulation_output,
        chain="Z",
        resname="LIG",
        skip_initial_structures=True,
    )
    analysis.generate(path="empty_reports")


@pytest.mark.parametrize(
    ("path", "traj", "top"),
    [
        (
            "analysis/data/xtc",
            "trajectory.xtc",
            "analysis/data/xtc/topologies/topology_0.pdb",
        ),
        ("analysis/data/empty_reports_output", "trajectory.pdb", None),
    ],
)
def test_residue_checker(path, traj, top):
    """
    Check, if we catch an error when the resname passed to Analysis doesn't exist in the output trajectories.

    Parameters
    -----------
    path : str
        Path to the simulation output folder.
    traj : str
        Trajectory type (as the user would set in the YAML), e.g. "trajectory.xtc".
    top : str
        Path to topology file.

    Raises
    --------
    ValueError if the residue name is not found in any of the trajectories.
    """
    simulation_output = os.path.join(test_path, path)
    topology = os.path.join(test_path, top) if top else None

    with pytest.raises(ValueError):
        analysis = Analysis(
            simulation_output=simulation_output,
            chain="Z",
            resname="STR",
            skip_initial_structures=True,
            traj=traj,
            topology=topology,
        )


@pytest.fixture
def generate_folders():
    """
    Generates a few random folders to test _check_existing_directory.
    """
    folder_template = "results_{}"
    folders = [folder_template.format(i) for i in range(3)] + ["results"]

    for folder in folders:
        try:
            os.mkdir(folder)
        except FileExistsError:
            pass


@pytest.fixture
def analysis():
    """
    Creates Analysis object to use in other tests.
    Returns
    -------
        Analysis object.
    """
    output = "../pele_platform/Examples/clustering"
    return get_analysis(output, None, None)


@pytest.mark.parametrize(
    ("yaml_file", "traj", "topology"),
    [
        ("input_sim.yaml", "pdb", None),
        # ("input_sim_xtc.yaml", "xtc", "pregrow/initialization_grow.pdb") TODO: Uncomment when Frag runs with XTC properly
    ],
)
def test_frag_API_analysis(yaml_file, traj, topology):
    """
    Runs frag simulation (both XTC and PDB) and checks, if it's possible to run Analysis via API.

    Parameters
    -----------
    yaml_file : str
        Base name of the input.yaml file in Examples/frag.
    traj : str
        Indicate if running "pdb" or "xtc".
    topology : str
        Path to the topology file, if running XTC simulation, otherwise None
    """
    # Run frag simulation
    yaml_file = os.path.join(test_path, "frag", yaml_file)
    job = main.run_platform_from_yaml(yaml_file)

    # Run analysis
    frag_folder = "1w7h_preparation_structure_2w_processed_frag_aminoC1N1"
    output = os.path.join(frag_folder, "sampling_result")
    analysis_output = f"analysis_{traj}"
    traj = f"trajectory.{traj}"

    if topology:
        topology = os.path.join(frag_folder, topology)

    analysis = Analysis(
        simulation_output=output, resname="GRW", chain="L", traj=traj, topology=topology
    )
    analysis.generate(analysis_output)

    # Check output
    assert len(glob.glob(os.path.join(analysis_output, "plots", "*png"))) > 0
    assert len(glob.glob(os.path.join(analysis_output, "clusters", "cluster*pdb"))) > 0

    shutil.rmtree(frag_folder, ignore_errors=True)


@pytest.mark.parametrize(("multi", "expected"), [(1, 2), (2, 4)])
def test_inner_clustering(analysis, multi, expected):
    """
    Checks if inner clustering is performed correctly.
    """
    working_folder = "inner_clustering"

    analysis.generate_clusters(
        working_folder,
        "meanshift",
        bandwidth=30,
        representatives_criterion="multi {}".format(multi),
    )

    results = glob.glob(os.path.join(working_folder, "*pdb"))
    results = [element for element in results if "water" not in element]

    assert len(results) == expected
    check_remove_folder(working_folder)
