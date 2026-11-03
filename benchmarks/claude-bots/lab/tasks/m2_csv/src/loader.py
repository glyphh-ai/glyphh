from parser import parse_rows


def load_people(text):
    rows = parse_rows(text)
    header, people = rows[0], []
    for row in rows[1:]:
        person = dict(zip(header, row))
        person["age"] = int(person["age"])
        people.append(person)
    return people
