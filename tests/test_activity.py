from app.services.activity import _events_for_transition


def test_calorie_transition_creates_meal_event() -> None:
    previous = {
        "healthy": True,
        "status": "online",
        "metrics": {"meal_count": 4, "calories": 1500, "calorie_goal": 2000},
    }
    current = {
        "healthy": True,
        "status": "online",
        "metrics": {"meal_count": 5, "calories": 2009, "calorie_goal": 2000},
    }
    events = _events_for_transition("calories", previous, current)
    assert events == [
        ("meal_logged", "Meal logged", "1 new meal logged • 2009 / 2000 kcal today")
    ]


def test_movie_transition_creates_new_inventory_event() -> None:
    previous = {
        "healthy": True,
        "status": "online",
        "metrics": {
            "title": "Dune: Part 3",
            "ticket_available": False,
            "theatres": [],
            "showtimes": [],
            "dates": [],
            "formats": [],
        },
    }
    current = {
        "healthy": True,
        "status": "online",
        "metrics": {
            "title": "Dune: Part 3",
            "ticket_available": True,
            "theatres": ["Cineplex Cinemas Kitchener and VIP"],
            "showtimes": ["7:00 pm"],
            "dates": ["Dec 18"],
            "formats": ["IMAX"],
        },
    }
    events = _events_for_transition("movies", previous, current)
    assert len(events) == 1
    assert events[0][0] == "movie_change"
    assert events[0][1] == "Dune: Part 3 tickets detected"
    assert "New showtimes: 7:00 pm" in events[0][2]
    assert "Cineplex Cinemas Kitchener and VIP" in events[0][2]


def test_home_assistant_presence_transition_creates_arrival_event() -> None:
    previous = {
        "healthy": True,
        "status": "online",
        "metrics": {
            "presence": [
                {"entity_id": "person.andy", "name": "Andy", "state": "not_home"}
            ]
        },
    }
    current = {
        "healthy": True,
        "status": "online",
        "metrics": {
            "presence": [
                {"entity_id": "person.andy", "name": "Andy", "state": "home"}
            ]
        },
    }
    events = _events_for_transition("home_assistant", previous, current)
    assert events == [
        ("presence_arrived", "Andy arrived home", "Presence changed to home.")
    ]


def test_github_transition_creates_failure_event() -> None:
    previous = {
        "healthy": True,
        "status": "online",
        "metrics": {
            "repos": [
                {
                    "repo": "MushroomStew01/stewy-os",
                    "name": "stewy-os",
                    "state": "success",
                    "workflow": "CI",
                }
            ]
        },
    }
    current = {
        "healthy": True,
        "status": "degraded",
        "metrics": {
            "repos": [
                {
                    "repo": "MushroomStew01/stewy-os",
                    "name": "stewy-os",
                    "state": "failure",
                    "workflow": "CI",
                }
            ]
        },
    }
    events = _events_for_transition("github", previous, current)
    assert events == [
        (
            "github_action_failed",
            "stewy-os Actions failed",
            "Latest CI run is failing.",
        )
    ]


def test_docker_transition_creates_unhealthy_event() -> None:
    previous = {
        "healthy": True,
        "status": "online",
        "metrics": {
            "containers": [
                {
                    "name": "stewy-os",
                    "state": "running",
                    "health": "healthy",
                }
            ]
        },
    }
    current = {
        "healthy": True,
        "status": "degraded",
        "metrics": {
            "containers": [
                {
                    "name": "stewy-os",
                    "state": "running",
                    "health": "unhealthy",
                }
            ]
        },
    }
    events = _events_for_transition("docker", previous, current)
    assert events == [
        (
            "container_unhealthy",
            "stewy-os is unhealthy",
            "Docker health check changed to unhealthy.",
        )
    ]


def test_system_transition_creates_storage_warning() -> None:
    previous = {
        "healthy": True,
        "status": "online",
        "metrics": {"disk_percent": 84.5},
    }
    current = {
        "healthy": True,
        "status": "online",
        "metrics": {"disk_percent": 85.2},
    }
    events = _events_for_transition("system", previous, current)
    assert events == [
        (
            "storage_warning",
            "Pi storage is getting full",
            "Root filesystem usage reached 85.2%.",
        )
    ]
