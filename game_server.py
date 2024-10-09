from collections import defaultdict
import random
from typing import Union
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import pika, sys, os, json
from fastapi.middleware.cors import CORSMiddleware
import uuid
from starlette.websockets import WebSocketState
import uvicorn
from enum import Enum
 
class GameState(Enum):
    NONE = 0
    PLAYING = 1
    WIN = 2
    DRAW = 3
    
class Move(BaseModel):
    player: str
    idx: int
    gameId: str

class Game:
    id: str
    name: str
    squares: []
    winner: str
    sockets: []
    gameState = GameState.NONE 
    players = []
    currentPlayer = ''
    numPlayers: int

    def __init__(self, name:str):
        self.id = str(uuid.uuid4())
        self.name = name
        self.squares = ['' for i in range(9)] 
        self.sockets = []
        self.players = []
        self.winner = ''
        self.gameState = GameState.NONE
        self.numPlayers = 0;

    async def endGame(self):
        self.squares = ['' for i in range(9)] 
        for socket in self.sockets:
            del socketMap[socket]
            if socket.client_state.name == WebSocketState.CONNECTED:
                await socket.close()
                
                print(f"client {socket.client.host} : {socket.client.port} has disconnected.")

        self.sockets = []
        self.gameState = GameState.NONE
        self.numPlayers = 0
        
    def assignPlayers(self):
        self.players.append(random.choice(['X', 'O']))

        if self.players[0] == 'X':
            self.players.append('O')
        else:
            self.players.append('X')

        self.currentPlayer = self.players[0]

    def startGame(self):
        self.squares = ['' for i in range(9)] 
        self.players = []
        self.winner = ''
        self.assignPlayers()
        self.gameState = GameState.PLAYING

    def switchPlayers(self):
        if self.currentPlayer == 'X':
            self.currentPlayer = 'O'
        else:
            self.currentPlayer = 'X'

app = FastAPI()

origins = [
    "http://localhost:4200",
    "https://localhost:4200",
    "http://127.0.0.1:4200",
    "https://127.0.0.1:4200",
    "https://ttt-ix4jjrfucq-uc.a.run.app",
    "https://ttt-735220675410.us-central1.run.app",
    "https://ttt.gerrenfrancis.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

lines = [
      [0, 1, 2],
      [3, 4, 5],
      [6, 7, 8],
      [0, 3, 6],
      [1, 4, 7],
      [2, 5, 8],
      [0, 4, 8],
      [2, 4, 6]
    ]

games = defaultdict(Game)

socketMap = {}

def joinGame(gameId: str):
    if gameId in games.keys():
        # connect to this game
        joinedId = games[gameId].id
    else:
        joinedId = createGame().id
   
    return joinedId

def createGame(name:str):
    game = Game(name)
    games[game.id] = game
    print(f'created game: {game.id}')

    return game

def join(gameId: str): 
    print(f'joining game: {gameId}')
    joinedId = joinGame(gameId)

    return joinedId

availableGames = {}

# [createGame('Game 1'), createGame('Game 2'), createGame('Game 3'),createGame('Game 4')]

def createAvailableGames(numGames: int):
    for i in range(1,numGames+1):
        game = createGame('Game ' + str(i))
        availableGames[game.id] = game

createAvailableGames(4)

def calculateWinner(game: Game):
    winner = None
    isDraw = False

    for  i in range(len(lines)):
        [a, b, c] = lines[i]
        if game.squares[a] != '' and game.squares[a] == game.squares[b] and game.squares[a] == game.squares[c]:
            winner = game.squares[a]
        
    if all(x != '' for x in game.squares)  and winner is None: 
        isDraw = True

    return (winner, isDraw)

async def makeMove(move: any, gameId: str):
    try:
        print(move)

        idx = move['idx']

        player = move['player']

        game = games[gameId]
        
        game.squares[idx] = player

        (winner, isDraw) = calculateWinner(game)

        if winner:
            game.gameState = GameState.WIN
            game.winner = winner
            # await game.endGame()
            print(f"Winner: {winner}")

        if isDraw:
            game.gameState = GameState.DRAW
            print("Draw!")

        for socket in game.sockets:
            await socket.send_json({"msg" : "make move", "move" : move, "squares" : game.squares, "isDraw" : isDraw, "gameState": game.gameState.name, "winner" : game.winner})

        game.switchPlayers()

        for socket in game.sockets:
            await socket.send_json({"msg" : "switch player", "player" : game.currentPlayer})

        
    except Exception as e:
        print(e)

async def endGame(gameId:str):
    for i, socket in enumerate(games[gameId].sockets):
        if socket.client_state != WebSocketState.DISCONNECTED:
            await socket.send_json({"msg" : "end game", "gameId" : gameId})

    await games[gameId].endGame()
    
async def notifyPlayerAdded(game:Game):
    for s in socketMap.keys():
        await s.send_json({"msg" : "player added","gameId": game.id, "numPlayers" : game.numPlayers})


# routes
@app.get("/")
def read_root():
    return "Nothing to see here... Move along."

@app.get("/freeGames")
def freeGames():
    returnList = []
    for game in availableGames.values():
        returnList.append(json.dumps({"id":game.id, "name":game.name, "numPlayers":game.numPlayers}))
   
    return json.dumps(returnList)

@app.websocket("/")
async def websocket_connect(websocket: WebSocket):
    try:
        await websocket.accept()
        socketMap[websocket] = None
    except Exception as e:
        print(e)
    
    while True:
        try:
            message = await websocket.receive_json()
           
            print(message)
            
            #figure out where to route
            if message['msg'] != None:
                match message['msg']:
                    case "new game":
                        # connect to existing game
                        gameId = next(iter(games.values())).id
                        
                        games[gameId].sockets.append(websocket)
                        
                        socketMap[websocket] = gameId

                        await websocket.send_json({"msg" : "new game", "gameId" : gameId})

                    case "join game":
                        gameId = message['gameId']
                       
                        joinedId = join(gameId)
                        
                        game = games[joinedId]

                        game.sockets.append(websocket)

                        socketMap[websocket] = gameId

                        if game.gameState != GameState.PLAYING:
                            game.startGame()

                        joinPlayer = ''

                        if len(game.sockets) == 1:
                            joinPlayer = game.players[0]
                            game.numPlayers = 1
                            availableGames[gameId].numPlayers = 1
                        else:
                            joinPlayer = game.players[1]
                            game.numPlayers = 2
                            availableGames[gameId].numPlayers = 2
                            
                        # for socket in game.sockets:
                        #     await socket.send_json({"msg" : "player added","gameId": gameId, "numPlayers" : game.numPlayers})
                        await notifyPlayerAdded(game)

                        await websocket.send_json({"msg" : "joined game", "gameId" : joinedId, "player" : joinPlayer, "selectedPlayer" : game.players[0]})

                    case "start game":
                        gameId = message['gameId']
                        
                        games[gameId].startGame()

                        for i, socket in enumerate(games[gameId].sockets):
                            await socket.send_json({"msg" : "start game", "gameId" : gameId, "selectedPlayer" : game.currentPlayer})

                    case "end game":
                        gameId = message['gameId']
                       
                        await endGame(gameId)

                    case "make move":
                        move = message['move']
                        
                        gameId = message['gameId']

                        await makeMove(move, gameId)

        except Exception as e:
            print(f"client {websocket.client.host} : {websocket.client.port} has disconnected.")
            if websocket in socketMap.keys():
                # await games[socketMap[websocket]].endGame()
                await endGame(socketMap[websocket])
          
            break 
        
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)