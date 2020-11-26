from pele_platform.Utilities.BuildingBlocks import blocks as bb


class AllostericLauncher:

    def __init__(self, env):
        self.env = env

    def run(self):
        """
        Launch allosteric simulation.
        1) Run global exploration to identify the most important pockets
        2) Run induced fit simulation to find deep pockets
        """
        self.env.package = "allosteric"
        result = bb.Pipeline([bb.GlobalExploration, bb.Selection, bb.InducedFitExhaustive], self.env).run()

        return result


