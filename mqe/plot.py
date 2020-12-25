import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
plt.rc('xtick', labelsize=14)
plt.rc('ytick', labelsize=14)
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

import shap



def plot_splits(self, dfs_y_train_split, dfs_y_valid_split=None):
    n_splits = len(dfs_y_train_split)
    fig, axes = plt.subplots(nrows=n_splits, ncols=1, sharex=True, figsize=(20,2.5*n_splits))

    axes = axes if isinstance(axes, np.ndarray) else [axes]
    for i in range(n_splits):
        df_train = dfs_y_train_split[i][0].groupby('valid_datetime').first().resample('H').first()
        axes[i].plot(df_train.index, df_train.values, label='train')
        if dfs_y_valid_split is not None: 
            df_valid = dfs_y_valid_split[i][0].groupby('valid_datetime').first().resample('H').first()
            axes[i].plot(df_valid.index, df_valid.values, label='valid')

        axes[i].set_title('split: {0}'.format(i+1), fontsize=14)
        axes[i].legend()

def plot_quantile_forecast(df_pred_site, df_y_site, start_time, end_time):
    df_plot_pred_site = df_pred_site.groupby('valid_datetime').last()[start_time:end_time].astype(float)
    df_plot_true_site = df_y_site.groupby('valid_datetime').last()[start_time:end_time].astype(float)
    
    sites = natural_sort(df_pred_site.columns.get_level_values(0).unique())
    quantiles = [quantile[8:] for quantile in df_pred_site.filter(regex='quantile').columns.get_level_values(1)]

    fig, ax = plt.subplots(nrows=len(sites), sharex=True, figsize=(16,4*len(sites)))
    if not isinstance(ax, np.ndarray): ax = [ax]
    
    for i, site in enumerate(sites): 
        df_plot_pred = df_plot_pred_site[site]
        df_plot_true = df_plot_true_site[site]
        alphas = np.linspace(0.01, 0.1, int(len(quantiles)/2))
        for j in range(int(len(quantiles)/2)):
            ax[i].fill_between(df_plot_pred.index, 
                               df_plot_pred['quantile'+quantiles[j+1]].values, 
                               df_plot_pred['quantile'+quantiles[len(quantiles)-j-1]].values,
                               color='b', linewidth=0.0, alpha=alphas[j])
        ax[i].plot(df_plot_pred.index, df_plot_pred['quantile50'].values, 'k--', label='median')
        ax[i].plot(df_plot_true.index, df_plot_true.values, 'k', label='real')

        ax[i].set_title('site {0}'.format(site))
        ax[i].set_ylabel('power', fontsize=14)
        plt.setp(ax[i].get_xticklabels(), rotation=30, ha='right')
        ax[i].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d-%Y'))
        ax[i].legend()
        ax[i].grid()
    
    return ax

def plot_scatters(df_y_pred_train, df_y_train, df_y_pred_valid=None, df_y_valid=None):
    columns = df_y_pred_train.columns
    if len(columns) == 1: 
        fig, axes = plt.subplots(figsize=(15,len(columns)))
    else: 
        fig, axes = plt.subplots(nrows=int(np.ceil(len(columns)/3)), ncols=3, sharex=True, sharey=True, figsize=(15,len(columns)))
    axes = axes.flatten()
    for column, ax in zip(columns,axes): 
        ax.scatter(df_y_pred_train[column], df_y_train[column], alpha=0.1)
        if (df_y_pred_valid is not None) and (df_y_valid is not None):
            ax.scatter(df_y_pred_valid[column], df_y_valid[column], alpha=0.1)


def plot_distributions(df_y_pred_train, df_y_train, df_y_pred_valid=None, df_y_valid=None): 
    columns = df_y_pred_train.columns
    if (df_y_pred_valid is not None) and (df_y_valid is not None):
        fig, axes = plt.subplots(nrows=len(columns), ncols=2, sharex=True, sharey=True, figsize=(15,2.4*len(columns)))
        a = 2
    else:
        fig, axes = plt.subplots(nrows=int(np.ceil(len(columns)/2)), ncols=2, figsize=(15,1.2*len(columns)))
        a = 1
    axes = axes.flatten()

    for i, column, in enumerate(columns): 
        axes[a*i].hist(df_y_train[column], bins=100, density=True, alpha=0.5)
        axes[a*i].hist(df_y_pred_train[column], bins=100, density=True, alpha=0.5)
        axes[a*i].set_title('train site {0}'.format(column))
        
        if (df_y_pred_valid is not None) and (df_y_valid is not None):
            axes[a*i+1].hist(df_y_valid[column], bins=100, density=True, alpha=0.5)
            axes[a*i+1].hist(df_y_pred_valid[column], bins=100, density=True, alpha=0.5)
            axes[a*i+1].set_title('valid site {0}'.format(column))
    
    fig.tight_layout()


def plot_mae_mse_lead_time(df_y_pred, df_y, pred_column='quantile50', kind='mse'): 
    df_pred = df_y_pred.filter(regex=pred_column).droplevel(1, axis=1)
    df_y = df_y.droplevel(1, axis=1)
    
    if kind == 'mae': 
        df_err = (df_pred-df_y).abs()
    elif kind == 'mse':
        df_err = (df_pred-df_y)**2

    df_err['lead_time'] = (df_err.index.get_level_values(1)-df_err.index.get_level_values(0))/pd.Timedelta(value='1H')
    df_err = df_err.groupby(by='lead_time').mean()
    ax = df_err.plot(figsize=(12,4))
    ax.set_ylabel(kind)

    return ax

def plot_mae_mse_timeofyear(df_y_pred, df_y, pred_column='quantile50', kind='mae'): 
    df_y_pred = df_y_pred.filter(regex='quantile50').droplevel(1, axis=1)
    df_y = df_y.droplevel(1, axis=1)

    if kind == 'mae': 
        df_err = (df_y_pred-df_y).abs()
    elif kind == 'mse':
        df_err = (df_y_pred-df_y)**2
    df_err = df_err.droplevel(0)  
    sites = natural_sort(df_err.columns.get_level_values(0).unique())

    for site in sites: 
        groups = df_err[site].groupby([df_err.index.hour, df_err.index.dayofyear])
        err = groups.mean().unstack().values
        plt.figure(figsize=(20,5))
        plt.imshow(err, cmap='viridis', aspect='auto')
        plt.colorbar()
        plt.xlabel('day of year', fontsize=14)
        plt.ylabel('hour of day', fontsize=14)

def plot_quantile_loss(dfs_loss):
    
    splits = range(len(dfs_loss))
    if len(splits) == 1: 
        fig, ax = plt.subplots(figsize=(10,5))
        ax = [ax]
    else:
        fig, ax = plt.subplots(nrows=int(np.ceil(len(splits)/3)), ncols=3, figsize=(20,15), sharex=True, sharey=True)
        ax = ax.flatten()
        
    for split in range(len(dfs_loss)): 
        df = dfs_loss[split].mean().unstack().T
        df.index = [float(index[8:]) for index in df.index]
        df = df.reindex(sorted(df.index), axis=0)
        df.plot(ax=ax[split], legend=True if split==0 else False)
        ax[split].set_title('split: {0}'.format(split), fontsize=14)
        ax[split].set_xlabel('quantile', fontsize=14)
        ax[split].set_ylabel('pinball loss', fontsize=14)


def natural_sort(l): 
    convert = lambda text: int(text) if text.isdigit() else text.lower() 
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ] 
    return sorted(l, key = alphanum_key)