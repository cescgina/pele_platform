import os
import pytest

from pele_platform.constants import constants
from pele_platform.Errors import custom_errors
from pele_platform.Checker import pdb_checker


test_path = os.path.join(constants.DIR, "Examples")


def test_protonation_error():
    """
    Checks if we catch unprotonated systems and raise an error.
    """
    file = os.path.join(constants.DIR, "Examples", "preparation/6qmk_correct.pdb")

    with pytest.raises(custom_errors.ProtonationError):
        pdb_checker.PDBChecker(file).check_protonation()


def test_missing_connects_error():
    """
    Checks if we raise an warning when PDB file is missing CONECT lines and create a new file with Schrodinger.
    """
    file = os.path.join(test_path, "constraints", "no_connects.pdb")
    expected_output = os.path.join(test_path, "constraints", "no_connects_conect.pdb")

    with pytest.warns(UserWarning):
        pdb_checker.PDBChecker(file).check_conects()

    assert os.path.exists(expected_output)
    os.remove(expected_output)


def test_negative_residues():
    """
    Checks if we raise an error, if we encounter a PDB with residue numbers < 1.
    """
    file = os.path.join(test_path, "checker", "negative_residues.pdb")

    with pytest.raises(custom_errors.IncorrectResidueNumbers):
        pdb_checker.PDBChecker(file).check_negative_residues()
