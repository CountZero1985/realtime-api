def magyar_ido_szoveggel(ora: str, perc: str) -> str:
    """
    Visszaadja az adott órát és percet magyar nyelven szöveges formában.

    Args:
        ora (str): Az óra (0-23).
        perc (str): A perc (0-59).
        
    Returns:
        str: Az idő szöveges formában.
    """
    
    # Speciális esetek kezelése
    if ora == 12 and perc == 0:
        return "dél"
    if ora == 0 and perc == 0:
        return "éjfél"
    if ora == 23 and perc == 59:
        return "éjfél előtt egy perccel"
    
    # 12 órás formátum és időszak meghatározása
    if ora == 0:
        ora_12 = 12
        idoszak = "éjjel"
    elif 1 <= ora < 6:
        ora_12 = ora
        idoszak = "éjjel"
    elif 6 <= ora < 12:
        ora_12 = ora
        idoszak = ""
    elif ora == 12:
        ora_12 = 12
        idoszak = "dél"
    elif 13 <= ora < 18:
        ora_12 = ora - 12
        idoszak = ""
    else:
        ora_12 = ora - 12
        idoszak = "este"
    
    # Következő óra számítása
    kovetkezo_ora = (ora_12 % 12) + 1
    
    # Számok szöveges formája
    szamok = {
        1: 'egy', 2: 'kettő', 3: 'három', 4: 'négy', 5: 'öt',
        6: 'hat', 7: 'hét', 8: 'nyolc', 9: 'kilenc', 10: 'tíz',
        11: 'tizenegy', 12: 'tizenkettő', 13: 'tizenhárom',
        14: 'tizennégy', 15: 'tizenöt', 16: 'tizenhat',
        17: 'tizenhét', 18: 'tizennyolc', 19: 'tizenkilenc',
        20: 'húsz', 21: 'huszonegy', 22: 'huszonkettő',
        23: 'huszonhárom', 24: 'huszonnégy', 25: 'huszonöt',
        26: 'huszonhat', 27: 'huszonhét', 28: 'huszonnyolc',
        29: 'huszonkilenc', 30: 'harminc', 31: 'harmincegy',
        32: 'harminckettő', 33: 'harminchárom', 34: 'harmincnégy',
        35: 'harmincöt', 36: 'harminchat', 37: 'harminchét',
        38: 'harmincnyolc', 39: 'harminckilenc', 40: 'negyven',
        41: 'negyvenegy', 42: 'negyvenkettő', 43: 'negyvenhárom',
        44: 'negyvennégy', 45: 'negyvenöt', 46: 'negyvenhat',
        47: 'negyvenhét', 48: 'negyvennyolc', 49: 'negyvenkilenc',
        50: 'ötven', 51: 'ötvenegy', 52: 'ötvenkettő',
        53: 'ötvenhárom', 54: 'ötvennégy', 55: 'ötvenöt',
        56: 'ötvenhat', 57: 'ötvenhét', 58: 'ötvennyolc',
        59: 'ötvenkilenc'
    }
    
    # Jelenlegi és következő óra szövegesen
    jelenlegi_ora = szamok[ora_12]
    kovetkezo_ora_szo = szamok[kovetkezo_ora]
    
    # Dél utáni percek speciális kezelése
    if idoszak == "dél" and perc != 0:
        jelenlegi_ora = "dél"
    
    # Percek szerinti formázás
    if perc == 0:
        if idoszak == "dél":
            return "dél"
        return f"{idoszak} {jelenlegi_ora}".strip()
    
    elif 1 <= perc <= 10:
        ido = f"{jelenlegi_ora} múlt {szamok[perc]} perccel"
    
    elif 11 <= perc <= 14:
        ido = f"negyed {kovetkezo_ora_szo} lesz {szamok[15 - perc]} perc múlva"
    
    elif perc == 15:
        ido = f"negyed {kovetkezo_ora_szo}"
    
    elif 16 <= perc <= 19:
        ido = f"negyed {kovetkezo_ora_szo} múlt {szamok[perc - 15]} perccel"
    
    elif 20 <= perc <= 29:
        ido = f"fél {kovetkezo_ora_szo} lesz {szamok[30 - perc]} perc múlva"
    
    elif perc == 30:
        ido = f"fél {kovetkezo_ora_szo}"
    
    elif 31 <= perc <= 39:
        ido = f"fél {kovetkezo_ora_szo} múlt {szamok[perc - 30]} perccel"
    
    elif 40 <= perc <= 44:
        ido = f"háromnegyed {kovetkezo_ora_szo} lesz {szamok[45 - perc]} perc múlva"
    
    elif perc == 45:
        ido = f"háromnegyed {kovetkezo_ora_szo}"
    
    elif 46 <= perc <= 52:
        ido = f"háromnegyed {kovetkezo_ora_szo} múlt {szamok[perc - 45]} perccel"
    
    elif 53 <= perc <= 59:
        ido = f"{szamok[60 - perc]} perc múlva {kovetkezo_ora_szo} óra"
    
    # Időszak hozzáfűzése
    if idoszak and idoszak != "dél":
        return f"{idoszak} {ido}"
    return ido
