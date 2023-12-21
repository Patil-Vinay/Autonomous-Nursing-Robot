"""Ward layout for the Robot page, in metres in the robot's map frame.

From scobo_gazebo/worlds/ward.world, map x = 7 - world x and map y = -1 - world y.
"""

# inside faces of the walls
ROOM = {'x0': -2.0, 'y0': -5.0, 'x1': 16.0, 'y1': 3.0}

# door in the east wall
DOOR = {'y0': -1.8, 'y1': -0.2}

# bed centres, 0.9 x 2.0 m, the head end against the nearer long wall
BED_SIZE = (0.9, 2.0)
BEDS = {
    1: (11.5, -3.9), 2: (8.5, -3.9), 3: (5.5, -3.9), 4: (2.5, -3.9),
    5: (2.5, 1.9), 6: (5.5, 1.9), 7: (8.5, 1.9), 8: (11.5, 1.9),
}

# bedside lockers, 0.5 x 0.5 m
LOCKERS = [
    (10.65, -4.7), (7.65, -4.7), (4.65, -4.7), (1.65, -4.7),
    (1.65, 2.7), (4.65, 2.7), (7.65, 2.7), (10.65, 2.7),
]

# (label, centre x, centre y, width, depth)
FURNITURE = [
    ('Nurse station', -1.6, -3.45, 0.7, 2.9),
    ('Trolley', -1.65, 1.2, 0.45, 0.6),
]


def layout(beds):
    """The plan with each bed's state: {number: {'occupied', 'initials', 'alert'}}."""
    return {
        'room': ROOM,
        'door': DOOR,
        'bed_size': BED_SIZE,
        'beds': [dict(number=n, x=x, y=y, **beds.get(n, {})) for n, (x, y) in BEDS.items()],
        'lockers': [{'x': x, 'y': y} for x, y in LOCKERS],
        'furniture': [{'label': label, 'x': x, 'y': y, 'w': w, 'h': h}
                      for label, x, y, w, h in FURNITURE],
    }
