from exercises import safe_exercises

def test_user_1_gets_safe_exercises(conn):
    result = safe_exercises(conn, 1)
    names = sorted(name for _id, name in result)
    assert names == ["Arm circles","Bird dog","Chair squat", "Jumping jacks" , "Reverse snow angels","Squats","Step-ups"] #"Burpees" is never in user 1’s results 

def test_user_2_gets_safe_exercises(conn):
    result = safe_exercises(conn, 2)
    names = sorted(name for _id, name in result)
    assert names == ["Dead bug","Jumping jacks","Knee push-up" , "Light dumbbell curls", "Reverse snow angels","Standing calf raise" , "Wall push-ups","Wall slide"]  # "Burpees" is never in user 2’s results

def test_user_3_gets_safe_exercises(conn):
    result = safe_exercises(conn, 3)
    names = sorted(name for _id, name in result)
    assert names == ["Dead bug","Jumping jacks","Knee push-up" ,  "Reverse snow angels","Standing calf raise" , "Wall push-ups","Wall slide"]

def test_user_4_gets_safe_exercises(conn):
    result = safe_exercises(conn, 4)
    names = sorted(name for _id, name in result)
    assert names == ["Arnold press","Barbell bent-over row","Barbell deadlift","Dragon flag" , "Dumbbell curls", "Dumbbell overhead press","Handstand push-up" ,"Heel taps","Incline push-up","Mountain climbers","One-arm dumbbell row","Pistol squat" ,"Push-ups", "Squats", "Superman","Triceps kickback" ,"Walking lunge"]  

def test_unknown_user_gets_no_exercises(conn):
    assert safe_exercises(conn, 999) == []