import math
from projection_providers.NBA_WNBA_Projections import NBA_WNBA_Projections, NBA_Projections_dk
import random
import datetime
import utils
import statistics
from ScrapeProcessManager import run
from Optimizer import FD_NBA_Optimizer, DK_NBA_Optimizer
import csv

# produce a table of projections
# generate an ensemble of rosters
# produce a file to upload


def parse_upload_template(csv_template_file, exclude, sport, offset = 0, entry_filter=None):
    template_file_lines = open(csv_template_file, "r").readlines()
    entries = []
    name_to_player_id = {}
    name_to_salary = {}
    player_id_to_name = {}
    player_id_to_fd_name = {}
    name_to_team = {}
    players_to_remove = []

    first_line = template_file_lines[0]
    for line in template_file_lines[1:]:
        parts = line.split(',')
        entry_id = parts[0].strip('"').strip()
        contest_id = parts[1].strip('"').strip()
        contest_name = parts[2].strip('"').strip().strip('"')

        if '"' in contest_name:
          __import__('pdb').set_trace()

        if entry_id != '' or contest_id != '' or contest_name != '':
            if entry_filter == None or entry_filter in contest_name:
                entries.append((entry_id, contest_id, contest_name))


        # __import__('pdb').set_trace()
        
        if len(parts) < 14:
            continue
    
        name_id = parts[13 - offset].strip('"').split(':')

        name_and_id = parts[13 - offset].strip('"')

        if len(name_id) == 1:
            continue
        injury_status = parts[25 - offset]

        player_id = name_id[0]
        fd_name = name_id[1]
        team = parts[23 - offset]
        salary = parts[21 - offset]
        name = utils.normalize_name(fd_name)

        name_to_player_id[name] = player_id
        name_to_team[name] = team
        name_to_salary[name] = salary

        player_id_to_name[player_id] = name
        
        player_id_to_fd_name[player_id] = name_and_id
        
        if name in exclude:
            players_to_remove.append(name)
            continue
        
        if sport == "MLB" and parts[30 - offset].strip() != "P" and parts[29 - offset] == '0':
          print("{} not in batting order".format(name))
          # __import__('pdb').set_trace()
          continue
        
        if injury_status == 'O' or injury_status == "IL" or injury_status == "NA":
            print("{} is OUT".format(name))
            players_to_remove.append(name)
            continue

    if len(player_id_to_name) == 0:
        # why??
        __import__('pdb').set_trace()

    return player_id_to_name, name_to_team, name_to_salary, name_to_player_id, first_line, entries, players_to_remove, player_id_to_fd_name

def get_name_to_player_objects(by_position):
  name_to_player_objects = {}
  for pos, players in by_position.items():
    for player in players:
      if not player.name in name_to_player_objects:
        name_to_player_objects[player.name] = []
      
      name_to_player_objects[player.name].append(player)

  return name_to_player_objects

def parse_existing_rosters(filepath):
  file = open(filepath)
  file_reader = csv.reader(file, delimiter=',', quotechar='"')
  entries = []
  first_line = True

  for parts in file_reader:
    if first_line:
      first_line = False
      continue
    player_ids = [a for a in parts]
    entries.append(player_ids)

  # TODO: potentially sort these by entry fee
  return entries

def filter_out_locked_teams(by_position, locked_teams):
  to_return = {}
  for pos, players in by_position.items():
    if not pos in to_return:
      to_return[pos] = []

    for player in players:
      if player.team in locked_teams:
        continue

      if player.value < 0.01:
        continue
      
      to_return[pos].append(player)
  
  return to_return

def construct_upload_template_file(rosters, first_line, entries, player_to_id, player_id_to_name, index_strings):
    timestamp = str(datetime.datetime.now())
    date = timestamp.replace('.', '_')
    date = date.replace(":", "_")
    output_file = open("/Users/amichailevy/Downloads/upload_template_{}.csv".format(date), "x")
    output_file.write(first_line)
    entry_idx = 0
    for entry in entries:
        cells = [entry[0], entry[1], entry[2].strip('"')]
        if entry_idx >= len(rosters):
            break
        roster = rosters[entry_idx]
        players = roster.players
        player_cells = []
        for player in players:
            player_id = player_to_id[player.name]

            player_name = player_id_to_name[player_id]

            player_cells.append(player_name)

        # player_cells.reverse()
        cells += player_cells

        # if len(cells) != 12:
        #     __import__('pdb').set_trace()

        to_write = ','.join(['"{}"'.format(c) for c in cells])
        if index_strings != None:
          to_write += ",{}".format(index_strings[entry_idx])

        output_file.write(to_write + "\n")
        entry_idx += 1
        

    output_file.close()

def get_players_by_value(by_position, team_set):
  all_players = []
  all_names = []
  name_to_position = {}
  for pos, players in by_position.items():
    for player in players:
      team = player.team
      if team not in team_set:
        continue

      name = player.name

      if not name in name_to_position:
        name_to_position[name] = ()

      name_to_position[name] += (pos,)

      if name in all_names:
        continue
      
      all_names.append(name)
      adjusted_value = round(player.value / player.cost * 100, 2)
      all_players.append((player, adjusted_value))

  all_players_with_position = []
  for player in all_players:

    player += (name_to_position[player[0].name],)
    all_players_with_position.append(player)

  all_players_sorted = sorted(all_players_with_position, key=lambda a: a[1], reverse=True)
  return all_players_sorted
  

def is_roster_valid(roster):
  team_ct = {}
  for pl in roster.players:
    team = pl.team
    if not team in team_ct:
      team_ct[team] = 1
    else:
      team_ct[team] += 1

    if team_ct[team] == 5:
      return False
    
  return True


def consider_swap(idx1, idx2, player1, player2, team_to_start_time):
  if team_to_start_time[player1.team] > team_to_start_time[player2.team]:
    pass
  pass

def optimize_dk_roster_for_late_swap(roster, start_times):
  team_to_start_time = {}
  for time, teams in start_times.items():
    for team in teams:
      team_to_start_time[team] = time

  players = roster.players
  # print("players before: {}".format(players))
  pg = players[0]
  sg = players[1]
  sf = players[2]
  pf = players[3]
  c = players[4]
  g = players[5]
  f = players[6]
  util = players[7]

  # __import__('pdb').set_trace()
  if team_to_start_time[pg.team] > team_to_start_time[g.team]:
    players[0] = g
    players[5] = pg
    pg = players[0]
    g = players[5]
  if team_to_start_time[sg.team] > team_to_start_time[g.team]:
    players[1] = g
    players[5] = sg
    sg = players[1]
    g = players[5]
  if team_to_start_time[sf.team] > team_to_start_time[f.team]:
    players[2] = f
    players[6] = sf
    sf = players[2]
    f = players[6]
  if team_to_start_time[pf.team] > team_to_start_time[f.team]:
    players[3] = f
    players[6] = pf
    pf = players[3]
    f = players[6]


  util_pos = util.position
  if util_pos == "PG":
    # try to swap with pg and g
    pass
  elif util_pos == "SG":
    # try to swap with sg and g
    pass
  elif util_pos == "SF":
    # try to swap with pf and f
    pass
  elif util_pos == "PF":
    # try to swap with pf and f
    pass
  elif util_pos == "C":
    # try to swap with c
    pass
  # latest_start_time = 0
  # latest_start_time_player = None
  # player_idx = 0
  # for i in range(4):
  #   player = players[i]
  #   start_time = team_to_start_time[player.team]
  #   if latest_start_time_player == None or start_time > latest_start_time:
  #     latest_start_time = start_time
  #     latest_start_time_player = player
  #     player_idx = i


  # __import__('pdb').set_trace()
  # players[7] = latest_start_time_player
  # players[player_idx] = util

  # print("players after: {}".format(players))


def generate_hedge_lineups(player_to_ct, by_position, optimizer, lineup_ct=20, iter=90000):
  
  hedge_projection_adjustments = {}
  max_ct = 0
  for _, ct in player_to_ct.items():
    if ct > max_ct:
      max_ct = ct
  for player, ct in player_to_ct.items():
    represenation = ct / max_ct
    to_subtract = represenation * 10
    factor = (100 - to_subtract) / 100
    hedge_projection_adjustments[player] = factor

  by_position_adjusted = {}
  for pos, players in by_position.items():
    if not pos in by_position_adjusted:
      by_position_adjusted[pos] = []
    for player in players:
      if player.name in hedge_projection_adjustments:
        by_position_adjusted[pos].append(utils.Player(player.name, player.position, player.cost, player.team, player.value * hedge_projection_adjustments[player.name], player.opp))
      else:
        by_position_adjusted[pos].append(player)
  
  rosters = optimizer.optimize_top_n(by_position_adjusted, lineup_ct, iter=iter)
  print("HEDGE ROSTER EXPOSURES")
  utils.print_player_exposures(rosters)
  return rosters

  

def optimize_slate_with_rosters(template_path, top_mme_rosters):
  player_id_to_name, _, _, name_to_player_id, first_line, entries, to_remove, player_id_to_fd_name = parse_upload_template(utils.DOWNLOAD_FOLDER + template_path, [], '', 0)


  entry_name_to_ct = {}
  for entry in entries:
    entry_name = entry[2]
    if not entry_name in entry_name_to_ct:
      entry_name_to_ct[entry_name] = 1
    else:
      entry_name_to_ct[entry_name] += 1


  to_print = []
  index_strings = []
  # distribute best roster to the single entry, and the rest to the MME
  entry_name_to_take_idx = {}

  for entry in entries:
    entry_name = entry[2]
    entry_ct = entry_name_to_ct[entry_name]

    if not entry_name in entry_name_to_take_idx:
      if entry_ct > 1:
        entry_name_to_take_idx[entry_name] = 1
      else:
        entry_name_to_take_idx[entry_name] = 0

    take_idx = entry_name_to_take_idx[entry_name]


    idx = take_idx % len(top_mme_rosters)
    roster_to_append = top_mme_rosters[idx]
    assert is_roster_valid(roster_to_append)
  
    to_print.append(roster_to_append)
    index_strings.append(str(idx) + "_MME_{}".format(roster_to_append.value))
    
    entry_name_to_take_idx[entry_name] += 1

  print("MME PLAYER EXPOSURES:")
  utils.print_player_exposures(top_mme_rosters)
  construct_upload_template_file(to_print, first_line, entries, name_to_player_id, player_id_to_fd_name, index_strings)

def generate_top_n_rosters_sorted(by_position, roster_count, iter):
  optimizer = FD_NBA_Optimizer()
  rosters = optimizer.optimize_top_n(by_position, roster_count, iter=iter)

  rosters_sorted = sorted(rosters, key=lambda a:a.value, reverse=True)

  return rosters_sorted


def filter_top_mme_rosters(rosters_sorted, value_tolerance, to_take):
  assert rosters_sorted[0].value >= rosters_sorted[1].value 
  assert rosters_sorted[10].value >= rosters_sorted[11].value 
  assert rosters_sorted[20].value >= rosters_sorted[21].value 

  value_couttoff = rosters_sorted[0].value - value_tolerance
  filtered_rosters = [r for r in rosters_sorted if r.value > value_couttoff]
  player_exposures = utils.get_player_exposures(filtered_rosters)
  player_to_new_value = {}

  for player, ct in player_exposures.items():
    player_to_new_value[player] = 1 / ct

  print("input rosters: {} filtered: {}".format(len(rosters_sorted), len(filtered_rosters)))
  if len(filtered_rosters) < to_take:
    print("Not enough rosters to take: {}".format(to_take))
    __import__('pdb').set_trace()
    filtered_rosters = rosters_sorted[:to_take]
    player_exposures = utils.get_player_exposures(filtered_rosters)

  roster_and_new_value = []
  idx = 0
  for roster in filtered_rosters:

    new_roster_value = sum([player_to_new_value[pl.name] for pl in roster.players])
    roster_and_new_value.append((roster, new_roster_value, idx))
    idx += 1
      
  roster_and_new_value_sorted = sorted(roster_and_new_value, key=lambda a: a[1], reverse=True)
  # for roster_val in roster_and_new_value_sorted:
  #   print("{} - {}, {}".format(round(roster_val[1], 2), roster_val[2], roster_val[0].value))

  
  all_the_new_rosters = [r[0] for r in roster_and_new_value_sorted]
  to_return = all_the_new_rosters[:to_take]

  # utils.print_player_exposures(rosters_sorted[:to_take])
  # print("------------")
  # utils.print_player_exposures(to_return)


  return to_return

def optimize_slate_v2(slate_path, template_path, iter, value_tolerance=5.6, validate_player_set=True):
  projections = NBA_WNBA_Projections(utils.DOWNLOAD_FOLDER + slate_path, "NBA")
  projections.print_slate()
  if validate_player_set:
    projections.validate_player_set()

  by_position = projections.players_by_position()

  # utils.save_player_projections(by_position)

  all_rosters_sorted = generate_top_n_rosters_sorted(by_position, roster_count=5000, iter=iter)
  # all_rosters_sorted = generate_top_n_rosters_sorted(by_position, roster_count=5000, iter=120000)


  all_rosters_sorted = [a for a in all_rosters_sorted if is_roster_valid(a)]

  SE_ROSTER_TAKE = 20
  se_rosters = all_rosters_sorted[:SE_ROSTER_TAKE]
  
  mme_rosters = filter_top_mme_rosters(all_rosters_sorted, value_tolerance=value_tolerance, to_take=150)
  # mme_rosters = filter_top_mme_rosters(all_rosters_sorted, value_tolerance=9, to_take=150)
  print("MME ROSTER COUNT: {}".format(len(mme_rosters)))
  assert len(mme_rosters) == 150

  player_id_to_name, _, _, name_to_player_id, first_line, entries, to_remove, player_id_to_fd_name = parse_upload_template(utils.DOWNLOAD_FOLDER + template_path, [], '', 0)


  entry_name_to_ct = {}
  for entry in entries:
    entry_name = entry[2]
    if not entry_name in entry_name_to_ct:
      entry_name_to_ct[entry_name] = 1
    else:
      entry_name_to_ct[entry_name] += 1

  entry_name_to_take_idx = {}
  index_strings = []
  to_print = []

  for entry in entries:
    entry_name = entry[2]
    entry_ct = entry_name_to_ct[entry_name]

    if not entry_name in entry_name_to_take_idx:
      if entry_ct > 1:
        entry_name_to_take_idx[entry_name] = 1
      else:
        entry_name_to_take_idx[entry_name] = 0

    take_idx = entry_name_to_take_idx[entry_name]

    if entry_ct <= SE_ROSTER_TAKE:
      idx = take_idx % len(se_rosters)
      roster_to_append = se_rosters[idx]
      if not is_roster_valid(roster_to_append):
        roster_to_append = se_rosters[idx + 1]
        assert is_roster_valid(roster_to_append)

      to_print.append(roster_to_append)
      index_strings.append(str(idx) + "_SE_{}".format(roster_to_append.value))
    else:
      idx = take_idx % len(mme_rosters)
      roster_to_append = mme_rosters[idx]
      # assert is_roster_valid(roster_to_append)
      
      to_print.append(roster_to_append)
      index_strings.append(str(idx) + "_MME_{}".format(roster_to_append.value))
    
    entry_name_to_take_idx[entry_name] += 1

  utils.print_player_exposures(to_print)

  construct_upload_template_file(to_print, first_line, entries, name_to_player_id, player_id_to_fd_name, index_strings)

def optimize_slate(slate_path, template_path, rosters_to_skip, iter, roster_filter=None, hedge_entry_name=None, hedge_entry_ct=0):
  projections = NBA_WNBA_Projections(utils.DOWNLOAD_FOLDER + slate_path, "NBA")
  projections.print_slate()
  projections.validate_player_set()


  by_position = projections.players_by_position()


  # # assert False
  player_id_to_name, _, _, name_to_player_id, first_line, entries, to_remove, player_id_to_fd_name = parse_upload_template(utils.DOWNLOAD_FOLDER + template_path, [], '', 0)


  entry_name_to_ct = {}
  for entry in entries:
    entry_name = entry[2]
    if not entry_name in entry_name_to_ct:
      entry_name_to_ct[entry_name] = 1
    else:
      entry_name_to_ct[entry_name] += 1


  rosters = []

  optimizer = FD_NBA_Optimizer()
  optimizer.optimize(by_position, None, iter)
  assert False

  rosters = optimizer.optimize_top_n(by_position, 5000, iter=iter)

  rosters_sorted = sorted(rosters, key=lambda a:a.value, reverse=True)
  orig_rosters_sorted = rosters_sorted
  if roster_filter != None:
    rosters_sorted = [r for r in rosters_sorted if roster_filter(r)]

  SE_ROSTER_TAKE = 20

  for roster in rosters_sorted[:SE_ROSTER_TAKE]:
    print(roster)

  # print("SE PLAYER EXPOSURES:")
  # utils.print_player_exposures(rosters_sorted[:SE_ROSTER_TAKE])


  mme_rosters = rosters_sorted
  print("MME ROSTERS RESOLVED: {}".format(len(mme_rosters)))
  valid_mme_rosters = [r for r in mme_rosters if is_roster_valid(r)]
  mme_rosters = valid_mme_rosters

  if len(mme_rosters) < 151:
    __import__('pdb').set_trace()

  top_mme_rosters = mme_rosters[rosters_to_skip:151 + rosters_to_skip]

  print("MME PLAYER EXPOSURES:")
  player_to_ct = utils.print_player_exposures(top_mme_rosters)

  # hedge_rosters = generate_hedge_lineups(player_to_ct, by_position, optimizer, 100, iter=50000)
  hedge_rosters = None

  to_print = []
  index_strings = []
  # distribute best roster to the single entry, and the rest to the MME
  entry_name_to_take_idx = {}
  invalid_roster_ct = 1

  for entry in entries:
    entry_name = entry[2]
    entry_ct = entry_name_to_ct[entry_name]

    IS_HEDGE_ENTRY = entry_name == hedge_entry_name \
      and entry_name in entry_name_to_take_idx \
      and entry_name_to_take_idx[entry_name] > hedge_entry_ct

    if not entry_name in entry_name_to_take_idx:
      if entry_ct > 1 and not IS_HEDGE_ENTRY:
        entry_name_to_take_idx[entry_name] = 1
      else:
        entry_name_to_take_idx[entry_name] = 0

    take_idx = entry_name_to_take_idx[entry_name]

    if IS_HEDGE_ENTRY:
      idx = (take_idx - hedge_entry_ct) % len(rosters_sorted)
      roster_to_append = hedge_rosters[idx]
      assert is_roster_valid(roster_to_append)

      to_print.append(roster_to_append)
      index_strings.append(str(idx) + "_HEDGE_{}".format(roster_to_append.value))

      entry_name_to_take_idx[entry_name] += 1
    elif entry_ct <= SE_ROSTER_TAKE:
      idx = take_idx % len(rosters_sorted)
      roster_to_append = rosters_sorted[idx]
      if not is_roster_valid(roster_to_append):
        roster_to_append = rosters_sorted[idx + 1]
        assert is_roster_valid(roster_to_append)

      to_print.append(roster_to_append)
      index_strings.append(str(idx) + "_SE_{}".format(roster_to_append.value))
    else:
      idx = take_idx % len(top_mme_rosters)
      roster_to_append = top_mme_rosters[idx]
      assert is_roster_valid(roster_to_append)
      
      to_print.append(roster_to_append)
      index_strings.append(str(idx) + "_MME_{}".format(roster_to_append.value))
    
      entry_name_to_take_idx[entry_name] += 1

  construct_upload_template_file(to_print, first_line, entries, name_to_player_id, player_id_to_fd_name, index_strings)

  return mme_rosters


def reoptimize_slate(slate_path, current_rosters_path, current_time, start_times, allow_duplicate_rosters=False):
  player_id_to_name, _, _, name_to_player_id, first_line, entries, to_remove, player_id_to_fd_name = parse_upload_template(utils.DOWNLOAD_FOLDER + current_rosters_path, [], '', 0)

  locked_teams = []
  for time, teams in start_times.items():
    if time < current_time:
      locked_teams += teams
  
  projections = NBA_WNBA_Projections(utils.DOWNLOAD_FOLDER + slate_path, "NBA")
  projections.print_slate()

  by_position = projections.players_by_position(exclude_zero_value=False)
  name_to_players = get_name_to_player_objects(by_position)
  optimizer = FD_NBA_Optimizer()

  by_position = filter_out_locked_teams(by_position, locked_teams)
  existing_rosters = parse_existing_rosters(utils.DOWNLOAD_FOLDER + current_rosters_path)
  seen_roster_strings = []
  seen_roster_string_to_optimized_roster = {}

  resolve_roster_keys = []

  roster_idx = 0
  all_results = []
  for existing_roster in existing_rosters:
    print("ROSTER: {}".format(roster_idx))
    roster_idx += 1
    players = existing_roster[3:12]
    if players[0] == '':
      continue

    roster_string = ",".join(players)

    if roster_string in seen_roster_strings:
      result = seen_roster_string_to_optimized_roster[roster_string]
      all_results.append(result)
      continue

    seen_roster_strings.append(roster_string)
    players3 = []
    for p in players:
      if ':' in p:
        p = p.split(':')[0]
      if not p in player_id_to_name:
        __import__('pdb').set_trace()

      players3.append(player_id_to_name[p])

    players4 = [name_to_players[p][0] for p in players3]
    players5 = []
    initial_roster = []
    lock_ct = 0
    for p in players4:
      if p.team in locked_teams:
        players5.append(p)
        lock_ct += 1
      else:
        players5.append(None)
      initial_roster.append(p.name)


    if lock_ct != 9:
      result = optimizer.optimize(by_position, players5, int(2150), is_roster_valid)
      # result = optimizer.optimize(by_position, players5, int(600))

    else:
      result = utils.Roster(players4)
    
    seen_roster_string_to_optimized_roster[roster_string] = result
    try:
      names1 = [p.name for p in result.players]
      roster1_key = ",".join(sorted(names1))

      is_se_roster = "Single Entry" in existing_roster[2] or "Entries Max" in existing_roster[2]
      if is_se_roster:
        print("IS SE ROSTER!")

      has_dead_player = any([a.value < 12.0 and a.team not in locked_teams for a in result.players])

      if roster1_key in seen_roster_strings \
          and not allow_duplicate_rosters \
          and not is_se_roster \
          and not has_dead_player:
        # don't change the result!
        print("initial roster unchanged! {}")
        all_results.append(utils.Roster(players4))
      else:
        seen_roster_strings.append(roster1_key)

        roster2_key = ",".join(sorted(initial_roster))
        if roster1_key != roster2_key:
          print("LOCKED PLAYERS: {}".format(players5))


          print("INITIAL ROSTER:\n{}".format(initial_roster))
          print(result)



        all_results.append(result)
    except:
      __import__('pdb').set_trace()

  total_roster_val = sum([a.value for a in all_results])
  utils.print_player_exposures(all_results, locked_teams)
  variation = utils.print_roster_variation(all_results)
  print(variation)
  
  # variation = utils.print_roster_variation(existing_rosters)
  # print(variation)
  print("TOTAL ROSTER VAL: {}".format(total_roster_val))
  

  construct_upload_template_file(all_results, first_line, entries, name_to_player_id, player_id_to_fd_name, None)


def single_game_optimizer():
  slate_path = "FanDuel-NBA-2022 ET-10 ET-29 ET-82506-players-list.csv"
  template_path = "FanDuel-NBA-2022-10-29-82506-entries-upload-template.csv"
  player_id_to_name, _, _, name_to_player_id, first_line, entries, to_remove, player_id_to_fd_name = parse_upload_template(utils.DOWNLOAD_FOLDER + template_path, [], '', 4)

  projections = NBA_WNBA_Projections(utils.DOWNLOAD_FOLDER + slate_path, "NBA")

  projections.print_slate()

  by_position = projections.players_by_position()

  all_results = utils.single_game_optimizer_many(by_position, 4)

  all_results_rosters = [utils.Roster(result[0]) for result in all_results]

  construct_upload_template_file(all_results_rosters * 1000, first_line, entries, name_to_player_id, player_id_to_fd_name, None)

def reoptimize_slate_dk(slate_path, entries_path, current_time, start_times):
  file = open(entries_path)
  file_reader = csv.reader(file, delimiter=',', quotechar='"')
  entries = []
  first_line = True
  for cells in file_reader:
    if first_line:
      first_line = False
      continue

    if cells[0] == '':
      break
    first_ten_cells = cells[:12]
    entries.append(first_ten_cells)

  projections = NBA_Projections_dk(utils.DOWNLOAD_FOLDER + slate_path, "NBA")
  projections.print_slate()
  locked_teams = []
  for time, teams in start_times.items():
    if time < current_time:
      locked_teams += teams

  by_position_unfiltered = projections.players_by_position()
  by_position = filter_out_locked_teams(by_position_unfiltered, locked_teams)

  name_to_player = {}
  for player in by_position_unfiltered['UTIL']:
    name_to_player[player.name] = player


  to_print = []
  optimizer = DK_NBA_Optimizer()
  for entry in entries:
    players = entry[4:12]
    locked_players = []
    for player in players:
      if "(LOCKED)" in player:
        name_stripped = utils.normalize_name(player.split('(')[0].strip())

        locked_players.append(name_to_player[name_stripped])
      else:
        locked_players.append('')
    optimized = optimizer.optimize(by_position, locked_players, 5000)
    to_print.append(optimized)
  utils.construct_dk_output_template(to_print, projections.name_to_player_id, entries_path)

def optimize_slate_dk(slate_path, iter, entries_path):
  # 
  projections = NBA_Projections_dk(utils.DOWNLOAD_FOLDER + slate_path, "NBA")
  projections.print_slate()

  by_position = projections.players_by_position()

  optimizer = DK_NBA_Optimizer()

  rosters = optimizer.optimize_top_n(by_position, 21, iter)
  for roster in rosters:
    optimize_dk_roster_for_late_swap(roster, start_times)
    print(roster)
  
  utils.construct_dk_output_template(rosters, projections.name_to_player_id, entries_path, "ls_unoptimized")

  for roster in rosters:
    # optimize_dk_roster_for_late_swap(roster, start_times)
    print(roster)
  
  utils.construct_dk_output_template(rosters, projections.name_to_player_id, entries_path, "ls_optimized")



##########################################################################################################
##########################################################################################################
##########################################################################################################



if __name__ == "__main__":
  (start_times, slate_path, template_path, dk_slate_path) = utils.load_start_times_and_slate_path('start_times.txt')
  
  ##FIRST PASS
  # all_rosters = optimize_slate_v2(slate_path, template_path, iter=90000, value_tolerance=8.0, validate_player_set=False)


  # entries_path = utils.DOWNLOAD_FOLDER + "DKEntries (5).csv"

  # all_rosters = optimize_slate_dk(dk_slate_path, 100000, entries_path)

  # assert False

  # SECOND PASS
  current_time = 8.1
  # reoptimize_slate(slate_path, "FanDuel-NBA-2022-11-12-83182-entries-upload-template (3).csv", current_time, start_times, allow_duplicate_rosters=False)

  reoptimize_slate_dk(dk_slate_path, utils.DOWNLOAD_FOLDER + "DKEntries (9).csv", current_time, start_times)

  assert False

  

#  port over lineup generator v2 - 
# make it easy to handle multiple slates simultaenously ('start_times.txt')
# properly sort players for dk lineups
# we need much better logging around our scraper - who is in, out etc