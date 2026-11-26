#!/usr/bin/env python3
"""Build the vehicle_specs tables for the RoXaS database.

Source for the spec rows: MazdaForum VIN decoder (2004 RX-8 4dr Cpe 6-Spd
Manual, saved as PDFs) plus build codes from the parts catalog. The VIN is NOT
stored in this file or the repo; pass it at run time and it goes only into the
private `vehicle_private` table of the output database.

    python3 build_vehicle_specs.py --db roxas.sqlite --vin <VIN>

Tables
  vehicle_specs(key, label, value, unit, metric_value, metric_unit,
                aliases, applies, source, note)
  vehicle_specs_fts   FTS5 over label + aliases (exact keyword lookup)
  vehicle_private(key, value)   VIN etc. Keep this DB file out of git.
"""
import argparse, sqlite3

DEC = "mazdaforum_decode"
CAT = "parts_catalog"

# (key, label, value, unit, aliases, applies, source, note)
ROWS = [
 # --- build codes (parts catalog) ---
 ("build_code", "Build code", "FE06", "", "build, fe06", 1, CAT, ""),
 ("paint_code", "Exterior paint code", "A3F", "", "paint, color, colour, exterior color, brilliant black", 1, CAT, "Brilliant Black"),
 ("interior_code", "Interior trim code", "FF4", "", "interior, interior color, interior colour, trim, seats, black red", 1, CAT, "Black/Red"),
 ("engine_code", "Engine code", "N3H6-02-000", "", "engine, high power, 6 port, six port", 1, CAT, "high-power 6-port Renesis"),
 ("transmission_code", "Transmission code", "Y610-17-01XG", "", "transmission, gearbox, manual, 6 speed", 1, CAT, "6-speed manual"),
 ("cabin_code", "Cabin number (sunroof, sport suspension)", "FE04-07-000", "", "cabin, sunroof, sport suspension", 1, CAT, ""),
 # --- engine and performance ---
 ("engine_type", "Engine", "1.3L RENESIS 2-rotor 6-intake-port rotary", "", "engine, motor, renesis, rotary", 1, DEC, "Gas rotary, MPI"),
 ("displacement", "Displacement", "1.3", "L", "engine size, displacement", 1, DEC, "13B-MSP, 80 ci"),
 ("horsepower", "Horsepower", "238 @ 8500", "hp @ rpm", "power, hp, horsepower", 1, DEC, "SAE net"),
 ("torque", "Torque", "159 @ 5500", "lb-ft @ rpm", "torque", 1, DEC, "SAE net"),
 ("alternator", "Maximum alternator capacity", "100", "A", "alternator, amps, charging", 1, DEC, ""),
 ("cooling_capacity", "Total cooling system capacity", "8.7", "qt", "coolant capacity, cooling system", 1, DEC, ""),
 ("fuel_tank", "Fuel tank capacity", "15.9", "gal", "fuel tank, gas tank, fuel capacity", 1, DEC, ""),
 ("oil_coolers", "Engine oil coolers", "Dual", "", "oil cooler", 1, DEC, "equipment list"),
 ("lsd", "Differential", "Limited slip", "", "differential, lsd, diff", 1, DEC, ""),
 # --- transmission and drive ---
 ("trans_type", "Transmission", "6-speed manual", "", "transmission, gearbox", 1, DEC, "Decoder text 'w/o OD' is a decoder quirk"),
 ("gear_1", "First gear ratio", "3.76", ":1", "first gear, 1st gear", 1, DEC, ""),
 ("gear_2", "Second gear ratio", "2.27", ":1", "second gear, 2nd gear", 1, DEC, ""),
 ("gear_3", "Third gear ratio", "1.65", ":1", "third gear, 3rd gear", 1, DEC, ""),
 ("gear_4", "Fourth gear ratio", "1.19", ":1", "fourth gear, 4th gear", 1, DEC, ""),
 ("gear_5", "Fifth gear ratio", "1.00", ":1", "fifth gear, 5th gear", 1, DEC, ""),
 ("gear_6", "Sixth gear ratio", "0.84", ":1", "sixth gear, 6th gear", 1, DEC, ""),
 ("gear_rev", "Reverse gear ratio", "3.56", ":1", "reverse gear", 1, DEC, ""),
 ("final_drive", "Final drive ratio", "4.44", ":1", "final drive, rear end, axle ratio", 1, DEC, ""),
 ("drivetrain", "Drivetrain", "Rear wheel drive", "", "drive, rwd, rear wheel drive, drivetrain", 1, DEC, ""),
 # --- wheels, tires, steering ---
 ("tires", "Tire size (front and rear)", "P225/45R18", "", "tires, tire size", 1, DEC, ""),
 ("wheels", "Wheel size (front and rear)", "18 x 8.0 alloy", "in", "wheels, rims, wheel size", 1, DEC, ""),
 ("steering_ratio", "Steering ratio", "16.43", ":1", "steering ratio", 1, DEC, ""),
 ("lock_to_lock", "Steering lock to lock", "2.99", "turns", "lock to lock", 1, DEC, ""),
 ("turn_curb", "Turning diameter, curb to curb", "34.8", "ft", "turning circle, turning radius", 1, DEC, ""),
 ("turn_wall", "Turning diameter, wall to wall", "36.8", "ft", "turning circle", 1, DEC, ""),
 # --- dimensions and weight ---
 ("curb_weight", "Base curb weight", "3029", "lb", "weight, curb weight, weigh, how heavy", 1, DEC, ""),
 ("wheelbase", "Wheelbase", "106.4", "in", "wheelbase", 1, DEC, ""),
 ("length", "Overall length", "174.3", "in", "length", 1, DEC, ""),
 ("width", "Overall width (without mirrors)", "69.7", "in", "width", 1, DEC, ""),
 ("height", "Overall height", "52.8", "in", "height", 1, DEC, ""),
 ("track_front", "Front track width", "58.9", "in", "track width front", 1, DEC, ""),
 ("track_rear", "Rear track width", "59.3", "in", "track width rear", 1, DEC, ""),
 ("ground_clearance", "Minimum ground clearance", "4.7", "in", "ground clearance, ride height", 1, DEC, ""),
 ("trunk_volume", "Trunk volume", "7.58", "ft3", "trunk, trunk space, cargo, boot space", 1, DEC, ""),
 ("passengers", "Passenger capacity", "4", "", "seats, passengers", 1, DEC, ""),
 # --- economy ---
 ("mpg_city", "EPA fuel economy, city", "18", "mpg", "mpg, fuel economy, city mileage, city gas mileage, city mpg", 1, DEC, ""),
 ("mpg_hwy", "EPA fuel economy, highway", "24", "mpg", "mpg, fuel economy, highway mileage, highway gas mileage, highway mpg", 1, DEC, ""),
 # --- other available options (not this car; kept for later) ---
 ("opt_paint_27c", "Available exterior color: Nordic Green Mica", "27C", "", "nordic green", 0, DEC, "not this car"),
 ("opt_paint_22v", "Available exterior color: Sunlight Silver Metallic", "22V", "", "sunlight silver, silver", 0, DEC, "not this car"),
 ("opt_paint_29y", "Available exterior color: Titanium Gray Metallic", "29Y", "", "titanium gray, grey", 0, DEC, "not this car"),
 ("opt_paint_27a", "Available exterior color: Velocity Red Mica", "27A", "", "velocity red, red", 0, DEC, "not this car"),
 ("opt_paint_27b", "Available exterior color: Winning Blue Metallic", "27B", "", "winning blue, blue", 0, DEC, "not this car"),
 ("opt_paint_a4j", "Available exterior color: Lightning Yellow", "A4J", "", "lightning yellow, yellow", 0, DEC, "not this car"),
 ("opt_int_ff5", "Available interior: Black/Chaparral", "FF5", "", "chaparral interior", 0, DEC, "not this car"),
 ("opt_int_ff3", "Available interior: Black (FF3)", "FF3", "", "black interior", 0, DEC, "not this car; cloth vs leather not stated"),
 ("opt_int_ff6", "Available interior: Black (FF6)", "FF6", "", "black interior", 0, DEC, "not this car; cloth vs leather not stated"),
]

# engine figures with no single-unit conversion are handled in rag/answer.py (hp -> kW, lb-ft -> N·m)
# imperial -> metric (voice defaults to imperial, metric on request)
CONV = {"lb": (0.45359237, "kg", 0), "gal": (3.785411784, "L", 1),
        "in": (25.4, "mm", 0), "qt": (0.946352946, "L", 1),
        "ft": (0.3048, "m", 1), "ft3": (28.316847, "L", 0),
        "mpg": (235.214583, "L/100km", 1)}   # 235.2 / mpg


def metric(value, unit):
    if unit not in CONV:
        return "", ""
    try:
        v = float(value)
    except ValueError:
        return "", ""
    f, mu, nd = CONV[unit]
    out = f / v if unit == "mpg" else f * v
    return f"{out:.{nd}f}", mu


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--vin", help="stored only in vehicle_private; never commit the DB")
    a = ap.parse_args()
    if not a.vin:     # data/derived/ is git-ignored, so the VIN can live there between rebuilds
        import os
        f = os.path.join(os.path.dirname(os.path.abspath(a.db)), "vin.txt")
        for cand in (f, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "derived", "vin.txt")):
            if os.path.exists(cand):
                a.vin = open(cand).read().strip(); break
    con = sqlite3.connect(a.db)
    cur = con.cursor()
    cur.executescript("""
    DROP TABLE IF EXISTS vehicle_specs;
    DROP TABLE IF EXISTS vehicle_specs_fts;
    CREATE TABLE vehicle_specs(
      key TEXT PRIMARY KEY, label TEXT NOT NULL, value TEXT NOT NULL,
      unit TEXT NOT NULL DEFAULT '', metric_value TEXT NOT NULL DEFAULT '',
      metric_unit TEXT NOT NULL DEFAULT '', aliases TEXT NOT NULL DEFAULT '',
      applies INTEGER NOT NULL DEFAULT 1, source TEXT NOT NULL, note TEXT NOT NULL DEFAULT '');
    CREATE VIRTUAL TABLE vehicle_specs_fts USING fts5(key UNINDEXED, label, aliases);
    CREATE TABLE IF NOT EXISTS vehicle_private(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    for key, label, value, unit, aliases, applies, source, note in ROWS:
        mv, mu = metric(value, unit)
        cur.execute("INSERT INTO vehicle_specs VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (key, label, value, unit, mv, mu, aliases, applies, source, note))
        cur.execute("INSERT INTO vehicle_specs_fts VALUES (?,?,?)", (key, label, aliases))
    if a.vin:
        cur.execute("INSERT OR REPLACE INTO vehicle_private VALUES ('vin', ?)", (a.vin,))
    con.commit()
    n = cur.execute("SELECT COUNT(*) FROM vehicle_specs").fetchone()[0]
    print(f"vehicle_specs: {n} rows; vin stored: {bool(a.vin)}")


if __name__ == "__main__":
    main()
