import constants
import logging
import time


class InvalidInputError(Exception):
  """Error used when the inputs fail to pass validation."""
  pass


# Mapping from a key name to where in Firebase it can be found
# along with a specific value that can be used to validate existance.
ENTITY_PATH = {
  'gameId': ['/games/%s', 'name'],
  'userToken': ['/users/%s', 'a'],
  'groupId': ['/groups/%s', 'gameId'],
  'playerId': ['/players/%s', 'userId'],
  'otherPlayerId': ['/players/%s', 'userId'],
  'gunId': ['/guns/%s', 'a'],
  'missionId': ['/missions/%s', 'name'],
  'chatRoomId': ['/chatRooms/%s', 'name'],
}


def ValidateInputs(request, firebase, required, valid):
  """Validate args.

  Keys in valid starting with a '!' are testing to ensure they do *not* exist.
  Any request item ending with Id eg 'fooId' must have a value starting 'foo-'

  Args:
    required: These args must be present in the request.
    valid: These args must already exist in the DB.

  Raises: InvalidInputError if validation does not pass.
  """
  if request is None:
    request = {}

  for key in required:
    if key[0] == '!':
      key = key[1:]
    if key not in request:
      raise InvalidInputError('Missing required input. Required: %s' % ', '.join(required))

  # Any keys fooId must start "foo-XXX"
  for key in request:
    if key.endswith('Id'):
      if not request[key].startswith('%s-' % key[:-2]):
        raise InvalidInputError('Id %s="%s" must start with "%s-".' % (
            key, request[key], key[:-2]))

  for key in valid:
    if key not in request:
      continue
    negate = False
    if key[0] == '!':
      negate = True
      key = key[1:]
    data = request[key]

    if key in ENTITY_PATH:
      path, item = ENTITY_PATH[key]
      val = firebase.get(path % data, item)
      if val is not None and negate:
        raise InvalidInputError('%s %s must not exist but was found.' % (key, data))
      elif not (val or negate):
        raise InvalidInputError('%s %s is not valid.' % (key, data))
    elif key == 'rewardCategoryId':
      path = '/games/%s/rewardCategories/%%s' % request['gameId']
      item = 'name'
      val = firebase.get(path % data, item)
      if val is not None and negate:
        raise InvalidInputError('%s %s must not exist but was found.' % (key, data))
      elif not (val or negate):
        raise InvalidInputError('%s %s is not valid.' % (key, data))
    elif key == 'rewardId':
      path = '/games/%s/rewardCategories/%s/rewards/%s' % (request['gameId'], request['rewardCategoryId'], data)
      if not firebase.get(path, None):
        raise InvalidInputError('Reward %s not found.' % data)
    elif key == 'allegiance':
      if data not in constants.ALLEGIANCES:
        raise InvalidInputError('Allegiance %s is not valid.' % data)
    else:
      raise InvalidInputError('Unhandled arg validation: "%s"' % key)


def Register(request, firebase):
  """Register a new user in the DB.

  Validation:
  Args:
    userToken: Unique user token added to the user list.

  Firebase entries:
    /users/%(userToken)
  """
  valid_args = ['!userToken']
  required_args = list(valid_args)
  ValidateInputs(request, firebase, required_args, valid_args)

  return firebase.put('/users', request['userToken'], {'a': True})


def CreateGame(request, firebase):
  """Create a new game.

  Validation:
    gameId must be valid format.

  Args:
    gameId:
    userToken:
    name:
    rulesHtml: static HTML containing the rule doc.
    stunTimer:

  Firebase entries:
    /games/%(gameId)
  """
  valid_args = ['!gameId']
  required_args = list(valid_args)
  required_args.extend(['userToken', 'name', 'rulesHtml', 'stunTimer'])
  ValidateInputs(request, firebase, required_args, valid_args)

  put_data = {
    'name': request['name'],
    'rulesHtml': request['rulesHtml'],
    'stunTimer': request['stunTimer'],
    'active': True,
    'adminUserId': request['userToken'],
  }
  return firebase.put('/games', request['gameId'], put_data)


def UpdateGame(request, firebase):
  """Update a game entry.

  Validation:

  Args:
    gameId:
    name (optional):
    rulesHtml (optional):
    stunTimer (optional):

  Firebase entries:
    /games/%(gameId)
  """
  valid_args = ['gameId']
  required_args = list(valid_args)
  ValidateInputs(request, firebase, required_args, valid_args)

  put_data = {}
  for property in ['name', 'rulesHtml', 'stunTimer']:
    if property in request:
      put_data[property] = request[property]

  return firebase.patch('/games/%s' % request['gameId'], put_data)


def CreateGroup(request, firebase):
  """Create a new player group.

  Validation:

  Args:
    groupId:
    gameId:
    allegiance:
    autoAdd:
    autoRemove:
    membersCanAdd:
    membersCanRemove:
    playerId: First player to add to the group.

  Firebase entries:
    /groups/%(groupId)
    /groups/%(groupId)/players/%(playerId)
    /games/%(gameId)/groups/%(groupId)
  """
  results = []
  valid_args = ['!groupId', 'gameId', 'playerId', 'allegiance']
  required_args = list(valid_args)
  required_args.extend(['autoAdd', 'autoRemove', 'membersCanAdd', 'membersCanRemove'])
  ValidateInputs(request, firebase, required_args, valid_args)

  put_args = list(required_args)
  put_args.remove('!groupId')
  put_args.remove('playerId')
  group_data = {k: request[k] for k in put_args}

  results.append(firebase.put('/groups', request['groupId'], group_data))
  results.append(firebase.put('/groups/%s/players' % request['groupId'], request['playerId'],  {'a': True}))
  results.append(firebase.put('/games/%s/groups/' % request['gameId'], request['groupId'], {'a': True}))

  return results


def UpdateGroup(request, firebase):
  """Update a group entry.

  Validation:

  Args:
    groupId:
    allegiance (optional):
    autoAdd (optional):
    autoRemove (optional):
    membersCanAdd (optional):
    membersCanRemove (optional):

  Firebase entries:
    /groups/%(groupId)
  """
  valid_args = ['groupId']
  required_args = list(valid_args)
  ValidateInputs(request, firebase, required_args, valid_args)

  put_data = {}
  for property in ['allegiance', 'autoAdd', 'autoRemove', 'membersCanAdd', 'membersCanRemove']:
    if property in request:
      put_data[property] = request[property]

  return firebase.patch('/groups/%s' % request['groupId'], put_data)


def CreatePlayer(request, firebase):
  """Create a new player for a user and put that player into the game.

  Player data gets sharded between /games/%(gameId)/players/%(playerId)
  and /players/%(playerId) for public and private info about players.
  The latter can be used to map a playerId to a gameId.

  Validation:
  Args:
    gameId:
    userToken:
    playerId:
    name:
    needGun:
    profileImageUrl:
    startAsZombie:
    volunteer:
    beSecretZombie:
    notifySound:
    notifyVibrate:

  Firebase entries:
    /players/%(playerId)
    /users/%(userToken)/players/%(playerId)
    /games/%(gameId)/players/%(playerId)
  """
  valid_args = ['gameId', 'userToken', '!playerId']
  required_args = list(valid_args)
  required_args.extend(['name', 'needGun', 'profileImageUrl'])
  required_args.extend(['startAsZombie', 'volunteer', 'beSecretZombie'])
  required_args.extend(['notifySound', 'notifyVibrate'])
  ValidateInputs(request, firebase, required_args, valid_args)

  results = []

  game = request['gameId']
  player = request['playerId']
  user_token = request['userToken']
  name = request['name']
  need_gun = request['needGun']
  profile_image_url = request['profileImageUrl']
  start_as_zombie = request['startAsZombie']
  volunteer = request['volunteer']
  be_secret_zombie = request['beSecretZombie']

  player_info = {'gameId': game}
  results.append(firebase.put('/users/%s/players' % user_token, player, player_info))

  player_info = {
    'gameId': game,
    'userId': user_token,
    'canInfect': start_as_zombie,
    'needGun' : need_gun,
    'startAsZombie' : start_as_zombie,
    'volunteer' : volunteer,
    'wantsToBeSecretZombie': be_secret_zombie,
    'notificationSettings': {
      'sound': request['notifySound'],
      'vibrate': request['notifyVibrate'],
    }
  }
  results.append(firebase.put('/players', player, player_info))

  if start_as_zombie:
    allegiance = 'horde'
  else:
    allegiance = 'resistence'

  game_info = {
    'user_id' : user_token,
    'name': name,
    'profileImageUrl' : profile_image_url,
    'points': 0,
    'allegiance': allegiance,
  }
  results.append(firebase.put('/games/%s/players' % game, player, game_info))

  return results


def UpdatePlayer(request, firebase):
  """Update player properties.

  Validation:
  Args:
    playerId:
    name (optional):
    needGun (optional):
    profileImageUrl (optional):
    startAsZombie (optional):
    volunteer (optional):
    notifySound:
    notifyVibrate:

  Firebase entries:
    /players/%(playerId)
    /games/%(gameId)/players/%(playerId)
  """
  results = []
  valid_args = ['playerId']
  required_args = list(valid_args)
  ValidateInputs(request, firebase, required_args, valid_args)

  player = request['playerId']
  game = firebase.get('/players/%s' % player, 'gameId')


  player_info = {}
  for property in ['startAsZombie', 'volunteer', 'needGun', 'wantsToBeSecretZombie']:
    if property in request:
      player_info[property] = request[property]
  player_info['notificationSettings'] = {}
  for property in ['notifySound', 'notifyVibrate']:
    if property in request:
      player_info['notificationSettings'][property] = request[property]

  game_info = {}
  for property in ['name', 'profileImageUrl', 'volunteer']:
    if property in request:
      game_info[property] = request[property]

  if player_info:
    results.append(firebase.patch('/players/%s' % player, player_info))
  if game_info:
    results.append(firebase.patch('/games/%s/players/%s' % (game, player), game_info))

  return results


def AddGun(request, firebase):
  """Add a new gun to the DB.

  Validation:
  Args:
    gunId: The ID of the gun.

  Firebase entries:
    /guns/%(gunId)/
  """
  valid_args = ['!gunId']
  required_args = list(valid_args)
  ValidateInputs(request, firebase, required_args, valid_args)

  return firebase.put('/guns', request['gunId'], {'playerId': '', 'a': True})


def AssignGun(request, firebase):
  """Assign a gun to a given player.

  Validation:
    Gun must exist.
    Player must exist.

  Args:
    playerId:
    gunId:

  Firebase entries:
    /guns/%(gunId)
  """
  valid_args = ['playerId', 'gunId']
  required_args = list(valid_args)
  ValidateInputs(request, firebase, required_args, valid_args)

  return firebase.put('/guns', request['gunId'], {'playerId': request['playerId']})


def AddMission(request, firebase):
  """Add a new mission.

  Validation:

  Args:
    missionId:
    groupId:
    name:
    begin:
    end:
    detailsHtml:

  Firebase entries:
    /missions/%(missionId)
  """
  valid_args = ['!missionId', 'groupId']
  required_args = list(valid_args)
  required_args.extend(['name', 'begin', 'end', 'detailsHtml'])
  ValidateInputs(request, firebase, required_args, valid_args)

  mission_data = {k: request[k] for k in required_args if k[0] != '!'}

  return firebase.put('/missions', request['missionId'], mission_data)


def UpdateMission(request, firebase):
  """Update details of a mission.

  Validation:
  Args:
    missionId
    name (optional):
    groupId:
    begin (optional):
    end (optional):
    detailsHtml (optional):

  Firebase entries:
    /missions/%(missionId)
  """
  valid_args = ['missionId', 'groupId']
  required_args = list(valid_args)
  ValidateInputs(request, firebase, required_args, valid_args)

  mission = request['missionId']

  put_data = {}
  for property in ['name', 'begin', 'end', 'detailsHtml', 'groupId']:
    if property in request:
      put_data[property] = request[property]

  return firebase.patch('/missions/%s' % mission, put_data)


def CreateChatRoom(request, firebase):
  """Create a new chat room.

  Use the chatId to make a new chat room.
  Add the player to the room and set the other room properties.
  Add the chatRoomId to the game's list of chat rooms.

  Validation:
  Args:
  Firebase entries:
    /chatRooms/%(chatRoomId)
    /chatRooms/%(chatRoomId)/memberships
    /games/%(gameId)/chatRooms
  """
  valid_args = ['!chatRoomId', 'gameId', 'playerId', 'groupId']
  required_args = list(valid_args)
  required_args.extend(['name'])
  ValidateInputs(request, firebase, required_args, valid_args)

  chat = request['chatRoomId']
  
  put_data = {
    'groupId': request['groupId'],
    'gameId': request['gameId'],
    'name': request['name'],
  }

  results = []
  results.append(firebase.put('/chatRooms', chat, put_data))
  results.append(firebase.put('/chatRooms/%s/memberships' % chat, request['playerId'], ""))
  results.append(firebase.put('/games/%s/chatRooms' % request['gameId'], chat, ""))
  return results


# TODO convert to add player to group?
def AddPlayerToChat(request, firebase):
  """Add a new player to a chat room.

  Validation:
    Player doing the adding is a member of the room.

  Args:
    chatRoomId: The chat room ID to add the player to.
    otherPlayerId: The player being added.
    playerId: The player doing the adding.

  Firebase entries:
    /chatRooms/%(chatRoomId)/memberships/%(playerId)
  """
  valid_args = ['chatRoomId', 'playerId', 'otherPlayerId']
  required_args = list(valid_args)
  ValidateInputs(request, firebase, required_args, valid_args)

  game = firebase.get('/players/%s', 'gameId')
  chat = request['chatRoomId']
  player = request['playerId']
  otherPlayer = request['otherPlayerId']

  # Validate player is in the chat room
  if firebase.get('/chatRooms/%s/memberships/%s' % (chat, player), None) is None:
    raise InvalidInputError('You are not a member of that chat room.')
  # Validate otherPlayer is not in the chat room
  if firebase.get('/chatRooms/%s/memberships' % chat, otherPlayer) is not None:
    raise InvalidInputError('Other player is already in the chat.')
  # TODO Check allegiance and other chat settings

  return firebase.put('/chatRooms/%s/memberships' % chat, otherPlayer, "")


def SendChatMessage(request, firebase):
  """Send a message to a chat room.

  Validation:
    Player is a member of the chat room.

  Args:
    chatRoomId: The chat room to update.
    playerId: The player sending the message.
    messageId: The ID of the new message.
    message: The message to add (string).

  Firebase entries:
    /chatRooms/%(chatRoomId)/memberships/%(playerId)
    /chatRooms/%(chatRoomId)/messages
  """
  valid_args = ['chatRoomId', 'playerId']
  required_args = list(valid_args)
  required_args.extend(['messageId', 'message'])
  ValidateInputs(request, firebase, required_args, valid_args)

  game = firebase.get('/players/%s', 'gameId')
  chat = request['chatRoomId']
  player = request['playerId']
  messageId = request['messageId']
  message = request['message']

  # TODO Map the chat to a group and check the group for membership
  # Validate player is in the chat room
  if firebase.get('/chatRooms/%s/memberships/%s' % (chat, player), None) is None:
    raise InvalidInputError('You are not a member of that chat room.')
  # TODO Validation the messageId is new.

  message_data = {
    'message': message,
    'playerId': player,
    'time': int(time.time()),
  }

  return firebase.put('/chatRooms/%s/messages' % chat, messageId, message_data)


def AddRewardCategory(request, firebase):
  """Add a new reward group.

  Validation:
    rewardCategoryId is of valid form.

  Args:
    gameId: The game ID. eg game-1
    rewardCategoryId: reward type, eg rewardCategory-foo
    name: Name of the reward
    limitPerPlayer: (int) how many a player can claim
    points: (int) points the reward is worth

  Firebase entries:
    /games/%(gameId)/rewardCategories/%(rewardCategoryId)
  """
  valid_args = ['gameId', '!rewardCategoryId']
  required_args = list(valid_args)
  required_args.extend(['name', 'points', 'limitPerPlayer'])
  ValidateInputs(request, firebase, required_args, valid_args)

  # TODO Validate the rewardCategoryId does not yet exist

  game = request['gameId']
  reward_category = request['rewardCategoryId']

  reward_category_data = {
    'claimed': 0,
    'name': request['name'],
    'points': int(request['points']),
    'limitPerPlayer': request['limitPerPlayer'],
  }

  return firebase.put('/games/%s/rewardCategories' % game, reward_category, reward_category_data)


def UpdateRewardCategory(request, firebase):
  """Update an existing reward group.

  Validation:
    rewardCategoryId exists.

  Args:
    gameId: The game ID. eg game-1
    rewardCategoryId: reward type, eg rewardCategory-foo
    name: Name of the reward
    limitPerPlayer: (int) how many a player can claim
    points: (int) points the reward is worth

  Firebase entries:
    /games/%(gameId)/rewardCategories/%(rewardCategoryId)
  """
  valid_args = ['gameId', 'rewardCategoryId']
  required_args = list(valid_args)
  ValidateInputs(request, firebase, required_args, valid_args)

  game = request['gameId']
  reward_category = request['rewardCategoryId']

  reward_category_data = {}
  for k in ('name', 'points', 'limitPerPlayer'):
    if k in request:
      reward_category_data[k] = request[k]

  return firebase.patch('/games/%s/rewardCategories/%s' % (game, reward_category), reward_category_data)


def AddReward(request, firebase):
  """Add a new reward to an existing category.

  Validation:

  Args:
    gameId: The game ID.
    rewardId: reward-foo-bar. Must start with the category, ie foo

  Firebase entries:
    /games/%(gameId)/rewardCategories/%(rCId)/rewards/%(rewardId)
  """
  valid_args = ['gameId']
  required_args = list(valid_args)
  required_args.extend(['rewardId'])
  ValidateInputs(request, firebase, required_args, valid_args)

  game = request['gameId']
  reward = request['rewardId']
  reward_seed = reward.split('-')[1]
  reward_category = 'rewardCategory-%s' % reward_seed
  path = '/games/%s/rewardCategories/%s/rewards' % (game, reward_category)

  # TODO Validation the rewardId does not yet exist
  if firebase.get('%s/%s' % (path, reward), 'a'):
    raise InvalidInputError('Reward %s already defined.' % reward)

  reward_data = {'playerId': '', 'a': True}

  return firebase.put(path, reward, reward_data)


def ClaimReward(request, firebase):
  """Claim a reward for a player.

  Validation:
    Reward is valid.
    Reward was not yet claimed.
    This player doesn't have the reward in their claims.

  Args:
    playerId: Player's ID
    rewardId: reward-foo-bar. Must start with the category

  Firebase entries:
    /games/%(gameId)/players/%(playerId)/claims/%(rewardId)
    /games/%(gameId)/players/%(playerId)/points
    /games/%(gameId)/rewardCategories/%(rCId)
    /games/%(gameId)/rewardCategories/%(rCId)/rewards/%(rewardId)
    /games/%(gameId)/rewardCategories/%(rCId)/rewards/%(rewardId)/playerId
  """
  valid_args = ['playerId']
  required_args = list(valid_args)
  required_args.extend(['rewardId'])
  ValidateInputs(request, firebase, required_args, valid_args)

  results = []

  player = request['playerId']
  reward = request['rewardId']
  game = firebase.get('/players/%s' % player, 'gameId')

  reward_category_seed = reward.split('-')[1]
  reward_category = 'rewardCategory-%s' % reward_category_seed

  player_path = '/games/%s/players/%s' % (game, player)
  reward_category_path = '/games/%s/rewardCategories/%s' % (game, reward_category)
  reward_path = '%s/rewards/%s' % (reward_category_path, reward)

  if not firebase.get(reward_path, None):
    raise InvalidInputError('Reward %s not found.' % reward)

  # Validate the user hasn't already claimed it.
  if firebase.get('%s/claims/%s' % (player_path, reward), 'time'):
    raise InvalidInputError('Reward was already claimed by this player.')
  # Validate the reward was not yet claimed by another player.
  if firebase.get(reward_path, 'playerId') != "":
    raise InvalidInputError('Reward was already claimed.')
  # Check the limitPerPlayer
  reward_limit = int(firebase.get(reward_category_path, 'limitPerPlayer'))
  if reward_limit:
    claims = firebase.get('%s/claims' % player_path, None)
    if claims:
      claims = [c for c in claims if c.startswith('reward-%s' % reward_category_seed)]
      if len(claims) >= reward_limit:
        raise InvalidInputError('You have already claimed this reward type %d times, which is the limit.' % reward_limit)

  results.append(firebase.patch(reward_path, {'playerId': player}))

  current_points = int(firebase.get(player_path, 'points'))
  reward_points = int(firebase.get(reward_category_path, 'points'))
  new_player_points = current_points + reward_points

  rewards_claimed = int(firebase.get(reward_category_path, 'claimed'))

  results.append('Player points = %d + %d => %d' % (current_points, reward_points, new_player_points))
  results.append('Claim count %d => %d' % (rewards_claimed, rewards_claimed + 1))
  results.append(firebase.patch(reward_category_path, {'claimed': rewards_claimed + 1}))
  results.append(firebase.patch(player_path, {'points': new_player_points}))
  results.append(firebase.patch(reward_path, {'playerId': player}))
  claim_data = {'rewardCategoryId': reward_category, 'time': int(time.time())}
  results.append(firebase.put('%s/claims' % player_path, reward, claim_data))

  return results


def DeleteTestData(request, firebase):
  if request['id'] != constants.FIREBASE_EMAIL:
    return
  
  root_entries = ('chatRooms', 'games', 'groups', 'guns', 'missions', 'players', 'users')
  for entry in root_entries:
    test_keys = [r for r in firebase.get('/%s' % entry, None) if 'test_' in r]
    for k in test_keys:
      firebase.delete('/%s' % entry, k)


def DumpTestData(request, firebase):
  if request['id'] != constants.FIREBASE_EMAIL:
    return
  
  res = {}
  root_entries = ('chatRooms', 'games', 'groups', 'guns', 'missions', 'players', 'users')
  for entry in root_entries:
    res[entry] = {}
    data = firebase.get('/%s' % entry, None)
    res[entry] = {r: data[r] for r in data if 'test_' in r}
  return res


# vim:ts=2:sw=2:expandtab
