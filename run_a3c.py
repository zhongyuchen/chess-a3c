import argparse
import os

import torch
import torch.multiprocessing as mp

from alphachess.config import Config
from alphachess.model import AlphaChess
from alphachess.rl.a3c import test, train
from alphachess.rl.shared_optim import SharedAdam

parser = argparse.ArgumentParser(description='A3C')
parser.add_argument('--lr', type=float, default=0.0001,
                    help='learning rate (default: 0.0001)')
parser.add_argument('--gamma', type=float, default=0.95,
                    help='discount factor for rewards (default: 0.95)')
parser.add_argument('--tau', type=float, default=1.00,
                    help='parameter for GAE (default: 1.00)')
parser.add_argument('--entropy-coef', type=float, default=0.01,
                    help='entropy term coefficient (default: 0.01)')
parser.add_argument('--value-loss-coef', type=float, default=0.5,
                    help='value loss coefficient (default: 0.5)')
parser.add_argument('--max-grad-norm', type=float, default=50,
                    help='value loss coefficient (default: 50)')
parser.add_argument('--seed', type=int, default=1,
                    help='random seed (default: 1)')
parser.add_argument('--num-processes', type=int, default=1,
                    help='how many training processes to use (default: 4)')
parser.add_argument('--num-steps', type=int, default=75,
                    help='number of forward steps in A3C (default: 75)')
parser.add_argument('--max-episode-length', type=int, default=1000000,
                    help='maximum length of an episode (default: 1000000)')
parser.add_argument('--env-name', default='PongDeterministic-v4',
                    help='environment to train on (default: PongDeterministic-v4)')
parser.add_argument('--no-shared', default=False,
                    help='use an optimizer without shared momentum.')


if __name__=="__main__":
    
    os.environ['CUDA_VISIBLE_DEVICES'] = ""  #disable GPU
    
    args = parser.parse_args()
    torch.manual_seed(args.seed)
    config = Config()
    config.rl.lr = args.lr 
    config.rl.gamma = args.gamma
    config.rl.tau = args.tau
    config.rl.entropy_coef = args.entropy_coef
    config.rl.value_loss_coef = args.value_loss_coef
    config.rl.max_grad_norm = args.max_grad_norm
    config.rl.num_processes = args.num_processes
    config.rl.num_steps = args.num_steps
    config.rl.max_episode_length = args.max_episode_length
    
    shared_model = AlphaChess(config)
    shared_model.share_memory()

    if args.no_shared:
        optimizer = None
    else:
        optimizer = SharedAdam(shared_model.parameters(), lr=args.lr)
        optimizer.share_memory()

    processes = []

    step_counter = mp.Value('i', 0)
    game_counter = mp.Value('i', 0)
    
    lock = mp.Lock()

    p = mp.Process(target=test, args=(args.num_processes, args, shared_model, step_counter, game_counter, lock, config))
    p.start()
    processes.append(p)

    for rank in range(0, args.num_processes):
        p = mp.Process(target=train, args=(rank, args, shared_model, step_counter, game_counter, lock, config, optimizer))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()