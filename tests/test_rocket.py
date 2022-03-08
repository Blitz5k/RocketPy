from unittest.mock import patch

import pytest
import numpy as np

from rocketpy import Environment, SolidMotor, Rocket, Flight


@patch("matplotlib.pyplot.show")
def test_rocket(mock_show):
    test_motor = SolidMotor(
        thrustSource="data/motors/Cesaroni_M1670.eng",
        burnOut=3.9,
        grainNumber=5,
        grainSeparation=5 / 1000,
        grainDensity=1815,
        grainOuterRadius=33 / 1000,
        grainInitialInnerRadius=15 / 1000,
        grainInitialHeight=120 / 1000,
        nozzleRadius=33 / 1000,
        throatRadius=11 / 1000,
        interpolationMethod="linear",
    )

    test_rocket = Rocket(
        motor=test_motor,
        radius=127 / 2000,
        mass=19.197 - 2.956,
        inertiaI=6.60,
        inertiaZ=0.0351,
        distanceRocketNozzle=-1.255,
        distanceRocketPropellant=-0.85704,
        powerOffDrag="data/calisto/powerOffDragCurve.csv",
        powerOnDrag="data/calisto/powerOnDragCurve.csv",
    )

    test_rocket.setRailButtons([0.2, -0.5])

    NoseCone = test_rocket.addNose(
        length=0.55829, kind="vonKarman", distanceToCM=0.71971
    )
    FinSet = test_rocket.addFins(
        4, span=0.100, rootChord=0.120, tipChord=0.040, distanceToCM=-1.04956
    )
    Tail = test_rocket.addTail(
        topRadius=0.0635, bottomRadius=0.0435, length=0.060, distanceToCM=-1.194656
    )

    def drogueTrigger(p, y):
        # p = pressure
        # y = [x, y, z, vx, vy, vz, e0, e1, e2, e3, w1, w2, w3]
        # activate drogue when vz < 0 m/s.
        return True if y[5] < 0 else False

    def mainTrigger(p, y):
        # p = pressure
        # y = [x, y, z, vx, vy, vz, e0, e1, e2, e3, w1, w2, w3]
        # activate main when vz < 0 m/s and z < 800 m.
        return True if y[5] < 0 and y[2] < 800 else False

    Main = test_rocket.addParachute(
        "Main",
        CdS=10.0,
        trigger=mainTrigger,
        samplingRate=105,
        lag=1.5,
        noise=(0, 8.3, 0.5),
    )

    Drogue = test_rocket.addParachute(
        "Drogue",
        CdS=1.0,
        trigger=drogueTrigger,
        samplingRate=105,
        lag=1.5,
        noise=(0, 8.3, 0.5),
    )

    assert test_rocket.allInfo() == None


def test_evaluate_static_margin_assert_cp_equals_cm(kg, m, dimensioneless_rocket):
    rocket = dimensioneless_rocket
    rocket.evaluateStaticMargin()

    assert rocket.centerOfMass(0) / (2 * rocket.radius) == rocket.staticMargin(0)
    assert rocket.centerOfMass(-1) / (2 * rocket.radius) == rocket.staticMargin(-1)
    assert rocket.totalLiftCoeffDer == 0
    assert rocket.cpPosition == 0


@pytest.mark.parametrize(
    "k, type",
    (
        [1 - 1 / 3, "conical"],
        [1 - 0.534, "ogive"],
        [1 - 0.437, "lvhaack"],
        [0.5, "default"],
        [0.5, "not a mapped string, to show default case"],
    ),
)
def test_add_nose_assert_cp_cm_plus_nose(k, type, dimensioneless_rocket, m):
    rocket = dimensioneless_rocket
    rocket.addNose(length=0.55829 * m, kind=type, distanceToCM=0.71971 * m)
    cpz = (0.71971 + k * 0.55829 ** 2) * m
    clalpha = 2

    static_margin_initial = (rocket.centerOfMass(0) - cpz) / (2 * rocket.radius)
    assert static_margin_initial == pytest.approx(rocket.staticMargin(0), 1e-12)

    static_margin_final = (rocket.centerOfMass(-1) - cpz) / (2 * rocket.radius)
    assert static_margin_final == pytest.approx(rocket.staticMargin(-1), 1e-12)

    assert clalpha == pytest.approx(rocket.totalLiftCoeffDer, 1e-12)
    assert rocket.cpPosition == pytest.approx(cpz, 1e-12)


def test_add_tail_assert_cp_cm_plus_tail(dimensioneless_rocket, m):
    rocket = dimensioneless_rocket
    rocket.addTail(
        topRadius=0.0635 * m, bottomRadius=0.0435 * m, length=0.060 * m, distanceToCM=-1.194656 * m
    )

    clalpha = -2 * (1 - (0.0635 / 0.0435) ** (-2)) * (0.0635 / (rocket.radius/m)) ** 2
    cpz = -1.194656 - (0.06 / 3) * (
        1 + (1 - (0.0635 / 0.0435)) / (1 - (0.0635 / 0.0435) ** 2)
    )
    cpz = cpz * m

    static_margin_initial = (rocket.centerOfMass(0) - cpz) / (2 * rocket.radius)
    assert static_margin_initial == pytest.approx(rocket.staticMargin(0), 1e-12)

    static_margin_final = (rocket.centerOfMass(-1) - cpz) / (2 * rocket.radius)
    assert static_margin_final == pytest.approx(rocket.staticMargin(-1), 1e-12)

    assert np.abs(clalpha) == pytest.approx(np.abs(rocket.totalLiftCoeffDer), 1e-8)
    assert rocket.cpPosition == cpz


def test_add_fins_assert_cp_cm_plus_fins(dimensioneless_rocket, m):
    rocket = dimensioneless_rocket
    rocket.addFins(
        4, span=0.100 * m, rootChord=0.120 * m, tipChord=0.040 * m, distanceToCM=-1.04956 * m
    )

    cpz = -1.04956 - (
        ((0.120 - 0.040) / 3) * ((0.120 + 2 * 0.040) / (0.120 + 0.040))
        + (1 / 6) * (0.120 + 0.040 - 0.120 * 0.040 / (0.120 + 0.040))
    )
    cpz = cpz * m

    clalpha = (4 * 4 * (0.1 / (2 * rocket.radius/m)) ** 2) / (
        1
        + np.sqrt(
            1
            + (2 * np.sqrt((0.12 / 2 - 0.04 / 2) ** 2 + 0.1 ** 2) / (0.120 + 0.040))
            ** 2
        )
    )
    clalpha *= 1 + rocket.radius / m / (0.1 + rocket.radius / m)

    static_margin_initial = (rocket.centerOfMass(0) - cpz) / (2 * rocket.radius)
    assert static_margin_initial == pytest.approx(rocket.staticMargin(0), 1e-12)

    static_margin_final = (rocket.centerOfMass(-1) - cpz) / (2 * rocket.radius)
    assert static_margin_final == pytest.approx(rocket.staticMargin(-1), 1e-12)

    assert np.abs(clalpha) == pytest.approx(
        np.abs(rocket.totalLiftCoeffDer), 1e-12
    )
    assert rocket.cpPosition == pytest.approx(cpz, 1e-12)


def test_add_cm_eccentricity_assert_properties_set(rocket):
    rocket.addCMEccentricity(x=4, y=5)

    assert rocket.cpEccentricityX == -4
    assert rocket.cpEccentricityY == -5

    assert rocket.thrustEccentricityY == -4
    assert rocket.thrustEccentricityX == -5


def test_add_thrust_eccentricity_assert_properties_set(rocket):
    rocket.addThrustEccentricity(x=4, y=5)

    assert rocket.thrustEccentricityY == 4
    assert rocket.thrustEccentricityX == 5


def test_add_cp_eccentricity_assert_properties_set(rocket):
    rocket.addCPEccentricity(x=4, y=5)

    assert rocket.cpEccentricityX == 4
    assert rocket.cpEccentricityY == 5


def test_set_rail_button_assert_distance_reverse(rocket):
    rocket.setRailButtons([-0.5, 0.2])
    assert rocket.railButtons == ([0.2, -0.5], 45)
