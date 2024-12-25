import csv

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


def main():
    lines = []
    with open("designations.csv", 'r', newline='') as file:
        reader = csv.DictReader(file, delimiter=';', quotechar='"')
        for row in reader:
            game = [
                row['\ufeff"Compétition"'],
                row['Phase'],
                row['Date'],
                months.get(row['Date'].split('/')[1], ''),
                row['Heure'],
                row['Lieu'],
                row['Rencontre'].split(' / ')[0].split(' - ', 1)[1],
                row['Rencontre'].split(' / ')[1].split(' - ', 1)[1],
            ]
            refCols = ['Arbitre principal', 'Arbitre principal 2', 'Juge de ligne', 'Juge de ligne 2', 'Arbitre', 'Arbitre 2', 'Superviseur']
            for col in refCols:
                ref = row[col]
                if ref:
                    cp = game.copy()
                    cp.extend([col.replace(" 2", ""), ref])
                    lines.append(cp)
    
    with open("template_design.html", 'r') as f:
        html_content = f.read()
    with open("data/designations.html", 'w') as f:
        f.write(html_content.replace("%DATA%", "\n".join(["<tr>" + "".join([f"<td>{data}</td>" for data in line]) + "</tr>" for line in lines])))

if __name__ == "__main__":
    main()