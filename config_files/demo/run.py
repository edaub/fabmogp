import numpy as np
import matplotlib.pyplot as plt
import mogp_emulator
from earthquake import create_problem, run_simulation, compute_moment
import sys
from pprint import pprint
from os.path import join

ed = mogp_emulator.LatinHypercubeDesign(
    [(-120., -80.), (0.1, 0.4), (0.9, 1.1)])


def run_mogp_simulation(sample_points, mpi_exec, fdfault_exec, results_dir):

    # We can now generate a design of sample_points by calling the sample
    np.random.seed(157374)
    input_points = ed.sample(sample_points)

    # Now we can actually run the simulations. First, we feed the input points
    # to create_problem to write the input files, call run_simulation to
    # actually simulate them, and compute_moment to load the data and compute
    # the earthquake size. The simulation is parallelized, so if you have
    # multiple cores available you can specify more processors to run the
    # simulation.
    counter = 1
    for point in input_points:
        name = "simulation_{}".format(counter)
        create_problem(point, name=name, output_dir=results_dir)
        run_simulation(name=name, n_proc=4, mpi_exec=mpi_exec,
                       fdfault_exec=fdfault_exec, output_dir=results_dir)
        counter += 1

    # save input_points array data into file
    np.save('input_points.npy', input_points)


def run_mogp_analysis(mpi_exec, fdfault_exec, results_dir):

    input_points = np.load(join(results_dir, "input_points.npy"))

    results = []
    counter = 1

    for point in input_points:
        name = "simulation_{}".format(counter)
        result = compute_moment(name=name, results_dir=results_dir)
        results.append(result)
        counter += 1

    results = np.array(results)

    # Now fit a Gaussian Process to the input_points and results to fit the
    # approximate model. We use the basic maximum martinal likelihood method
    # to estimate the GP hyperparameters
    gp = mogp_emulator.GaussianProcess(input_points, results)
    gp.learn_hyperparameters()

    # We can now make predictions for a large number of input points much
    # more quickly than running the simulation.
    query_points = ed.sample(1000)
    predictions = gp.predict(query_points)

    # predictions contains both the mean values and variances from the
    # approximate model, so we can use this to quantify uncertainty given
    # a known value of the moment.
    # Since I don't have an actual observation to use, I will do a synthetic
    # test by running an additional point so I can evaluate the results from
    # the known inputs.
    known_input = ed.sample(1)
    name = "known_value"
    create_problem(known_input[0], name=name, output_dir=results_dir)
    run_simulation(name=name, n_proc=4, mpi_exec=mpi_exec,
                   fdfault_exec=fdfault_exec, output_dir=results_dir)
    known_value = compute_moment(name=name, results_dir=results_dir)

    # One easy method for comparing a model with observations is known as
    # History Matching, where you compute an implausibility measure for many
    # sample points given all sources of uncertainty (observational error,
    # approximate model uncertainty, and "model discrepancy" which is a measure
    # of how good the model is at describing reality). For simplicity here we
    # will only consider the approximate model uncertainty, but for real
    # situations it is important to include all three sources.
    # The implausibility is then just the number of standard deviations between
    # the predicted value and the known value.

    # To compute the implausibility, we use the HistoryMatching class, which
    # requires the observation, query points (coords), and predicted values
    # (expectations), plus a threshold above which we can rule out a point

    hm = mogp_emulator.HistoryMatching(obs=known_value, coords=query_points,
                                       expectations=predictions, threshold=2.)

    implaus = hm.get_implausibility()

    # We can see which points have not been ruled out yet (NROY) based on the
    # implausibility threshold.

    print("Actual point:", known_input[0])
    print("NROY:")
    print(query_points[hm.get_NROY()])


if __name__ == "__main__":

    # Parse command line options
    mood = sys.argv[1]
    if mood == "run_simulation":
        mpi_exec = sys.argv[2]
        fdfault_exec = sys.argv[3]
        results_dir = sys.argv[4]

        try:
            sample_points = int(sys.argv[5])
        except ValueError:
            print("Error : input sample points should be integer value !")
            exit()

        print("\n\t\tmood = " + mood + '\t' + str(type(mood)))
        print("\t\tsample_points = " + str(sample_points) +
              '\t' + str(type(sample_points)))
        run_mogp_simulation(sample_points, mpi_exec,
                            fdfault_exec, results_dir)
    elif mood == "analysis":
        mpi_exec = sys.argv[2]
        fdfault_exec = sys.argv[3]
        results_dir = sys.argv[4]

        run_mogp_analysis(mpi_exec, fdfault_exec, results_dir)
