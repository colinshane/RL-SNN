import brian2 as b
import numpy as np

import env
from models.neurons import LIF
from models.synapses import GapRL, Activator


def visualise_connectivity(S):
    Ns = len(S.source)
    Nt = len(S.target)
    b.figure(figsize=(10, 4))
    b.subplot(121)
    b.plot(b.zeros(Ns), b.arange(Ns), 'ok', ms=10)
    b.plot(b.ones(Nt), b.arange(Nt), 'ok', ms=10)
    for i, j in zip(S.i, S.j):
        b.plot([0, 1], [i, j], '-k')
    b.xticks([0, 1], ['Source', 'Target'])
    b.ylabel('Neuron index')
    b.xlim(-0.1, 1.1)
    b.ylim(-1, max(Ns, Nt))
    b.subplot(122)
    b.plot(S.i, S.j, 'ok')
    b.xlim(-1, Ns)
    b.ylim(-1, Nt)
    b.xlabel('Source neuron index')
    b.ylabel('Target neuron index')


@b.check_units(idx=1, result=b.Hz)
def inp_rates(idx):
    la, ra = e.obs()
    la = la.repeat(2)
    ra = ra.repeat(2)
    l_idx = b.arange(len(idx), step=2)
    r_idx = l_idx + 1
    r = np.zeros(len(idx))
    r[l_idx] = la / theta_max * 50
    r[r_idx] = ra / theta_max * 50
    return r * b.Hz


@b.check_units(voltage=b.volt, dt=b.second, result=1)
def sigma(voltage, dt):
    sv = dt / tau_sigma * b.exp(beta_sigma * (voltage - th_i))
    sv.clip(0, 1)
    return sv


@b.check_units(idx=1, result=1)
def get_reward(idx):
    return e.r


@b.check_units(activation=1, idx=1, result=1)
def act(activation, idx):
    activation.clip(0, 1)
    l_idx = b.arange(len(idx), step=2)
    r_idx = l_idx + 1

    a_avg = (activation[l_idx] + activation[r_idx]) / 2

    l_idx = b.arange(len(a_avg), step=2)
    r_idx = l_idx + 1

    theta = (a_avg[l_idx] - a_avg[r_idx]) * theta_max
    e.step(theta)
    return 0


b.defaultclock.dt = 0.1 * b.ms
b.prefs.codegen.target = 'numpy'

num_parts = 20
theta_max = 25.0
e = env.WormFoodEnv((2, 3), num_parts=num_parts, theta_max=theta_max)

N_i = num_parts * 4
N_h = 200
N_o = num_parts * 4

inp_eq = 'rates: Hz '
inp_th = 'rand() < rates*dt'

inp_group = b.NeuronGroup(N_i, inp_eq, threshold=inp_th)
inp_group.run_regularly('rates=inp_rates(i)', dt=b.defaultclock.dt)

tau_i = 20 * b.ms  # Time constant for LIF leak
v_r = 10 * b.mV  # Reset potential
th_i = 16 * b.mV  # Threshold potential
tau_sigma = 20 * b.ms
beta_sigma = 0.2 / b.mV
lif = LIF(tau_i, v_r, sigma, tau_sigma, beta_sigma)

neuron_group = b.NeuronGroup(N_h + N_o, lif.equ, threshold=lif.threshold, reset=lif.reset)
hidden_group = neuron_group[:N_h]
op_group = neuron_group[N_h:]

tau_z = 5 * b.ms
w_min_i = -0.1 * b.mV
w_max_i = 1.5 * b.mV
gamma_i = 0.025 * (w_max_i - w_min_i) * b.mV
syn_ih = GapRL(get_reward, sigma, tau_z, tau_i, gamma_i, w_min_i, w_max_i, beta_sigma)

w_min = -0.4 * b.mV
w_max = 1 * b.mV
gamma = 0.025 * (w_max - w_min) * b.mV
syn_hh = GapRL(get_reward, sigma, tau_z, tau_i, gamma, w_min, w_max, beta_sigma)

ih_group = b.Synapses(inp_group, neuron_group, model=syn_ih.model, on_pre=syn_ih.on_pre, on_post=syn_ih.on_post)
hh_group = b.Synapses(neuron_group, neuron_group, model=syn_hh.model, on_pre=syn_hh.on_pre, on_post=syn_hh.on_post)

ih_group.connect(p=0.15)
hh_group.connect(p=0.15)

ih_group.w = np.random.uniform(w_min_i, w_max_i, ih_group.w.shape) * b.volt
hh_group.w = np.random.uniform(w_min, w_max, hh_group.w.shape) * b.volt

ih_group.run_regularly('z1 = z', dt=b.defaultclock.dt)
ih_group.run_regularly('w = clip(w + gamma * r * z, w_min, w_max)', dt=b.defaultclock.dt)
hh_group.run_regularly('z1 = z', dt=b.defaultclock.dt)
hh_group.run_regularly('w = clip(w + gamma * r * z, w_min, w_max)', dt=b.defaultclock.dt)

act_n_eq = '''a : 1
        dummy : 1
        '''
act_group = b.NeuronGroup(N_o, act_n_eq)
act_group.run_regularly('dummy = act(a, i)', dt=b.defaultclock.dt)

tau_e = 2 * b.second
nu_e = 25 * b.Hz
syn_oa = Activator(tau_e, nu_e)
oa_group = b.Synapses(op_group, act_group, model=syn_oa.model, on_pre=syn_oa.on_pre)
oa_group.connect(j='i')

# spikemon = b.SpikeMonitor(inp_group)
# M = b.StateMonitor(inp_group, 'rates', record=True)
# M1 = b.StateMonitor(hidden_group, 'v', record=True)
#
# print ih_group.w, hh_group.w
print e.disToFood
b.run(10 * b.second)
print e.disToFood
# print ih_group.w, hh_group.w
#
# b.figure()
# b.plot(spikemon.t / b.second, spikemon.i, '.k')
# b.xlabel('Time (in s)')
# b.ylabel('Neuron index')

# b.figure()
# for ri in M.rates:
#     b.plot(M.t / b.ms, ri / b.Hz)

# b.figure()
# for v in M1.v:
#     b.plot(M.t / b.ms, v / b.mV)
#
# b.show()