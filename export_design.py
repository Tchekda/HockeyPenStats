import csv
import re
from get_design import main as get_design

months = {
    '01': 'Janvier',
    '02': 'Février',
    '03': 'Mars',
    '04': 'Avril',
    '05': 'Mai',
    '06': 'Juin',
    '07': 'Juillet',
    '08': 'Août',
    '09': 'Septembre',
    '10': 'Octobre',
    '11': 'Novembre',
    '12': 'Décembre',
}


ref_roles = {
    6: 'Arbitre principal',
    7: 'Juge de ligne',
    8: 'Arbitre',
    9: 'SuperViseur',
}

def main():
    lines = []
    designations = get_design().splitlines()
    print("Fetched", len(designations) - 1, "designations")
    reader = csv.reader(designations, delimiter=';', quotechar='"')
    next(reader) # Skip header
    for row in reader:
        game = [
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
        ]
        for teamId in [0, 1]:
            teamCp = game.copy()
            teamCp.extend(["Domicile" if teamId == 0 else "Visiteur", row[5].split(' / ')[teamId].split(' - ', 1)[1]])
            refCols = [6, 7, 8, 9]
            for col in refCols:
                ref = row[col]
                if ref:
                    refNames = ref.split(', ')
                    for refName in refNames:
                        refCp = teamCp.copy()
                        refMatch = re.match(r"M(?:me)? ([A-Z \-']+) ([A-Z][\w \-']+)", refName)
                        if refMatch:
                            lastName = refMatch.group(1)
                            firstName = refMatch.group(2)
                            refCp.extend([ref_roles.get(col, "Arbitre"), lastName, firstName])
                            lines.append(refCp)
                        else:
                            print("Error: referee name does not match the expected format", ref)
    print("Processed", len(lines), "designations entries")
    with open("template_design.html", 'r') as f:
        html_content = f.read()
    with open("data/designations.html", 'w') as f:
        f.write(html_content.replace("%DATA%", "\n".join(["<tr>" + "".join([f"<td>{data}</td>" for data in line]) + "</tr>" for line in lines])))

if __name__ == "__main__":
    main()