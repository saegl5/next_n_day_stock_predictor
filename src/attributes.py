import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
plt.style.use('fivethirtyeight')
import seaborn as sns

import pandas_datareader.data as web

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV
import joblib

from sklearn.metrics import (roc_auc_score
                             , precision_score
                             , recall_score
                             , roc_curve
                             , confusion_matrix
                             , plot_confusion_matrix
                             , precision_recall_curve
                             , auc
                            )

from sklearn.utils import resample
from sklearn.model_selection import cross_val_score


def data(stock, start_date, days_ahead):
    """
    Inputs: stock, string of stock symbol
            start_date, string of stock origination date in form 'MM/DD/YYYY'
            days_ahead, int days prediction ahead, 1 for 1 day ahead, 2 for 2 days ahead, etc...
    Output: X_train, X_test, y_train, y_test for modeling
    """
    
    # download daily stock data from yahoo 
    stock_df = web.DataReader(stock
                              , 'yahoo'
                              , start = start_date
                             )
    
    # open close % difference
    stock_df['oc'] = (stock_df.Open - stock_df.Close) / stock_df.Open
    
    # high low % difference
    stock_df['hl'] = (stock_df.High - stock_df.Low) / stock_df.Low
    
    # adjusted close % change from previous day
    stock_df['adj'] = stock_df['Adj Close'].pct_change()
    
    # 5 day standard deviation of adjusted close % change from previous day 
    stock_df['5stdev_adj'] = stock_df.adj.rolling(5).std()
    
    # 5 day rolling average of adjusted close % change from pervious day
    stock_df['5sma_adj'] = stock_df.adj.rolling(5).mean()
    
    # Direction
    stock_df['direction'] = np.where(stock_df.adj.shift(-days_ahead) > stock_df.adj, 1, -1)
    
    # drop nulls
    stock_df.dropna(axis=0, inplace=True)    
    
    # split stock_df to train test dataframes
    split = int(stock_df.shape[0] * 0.75)
    train = stock_df[:split]
    test = stock_df[split:]
    
    # upsample class inbalance for 'direction' 
    train_major = train[train['direction'] == -1]
    train_minor = train[train['direction'] == 1]

    train_minor_upsampled = resample(train_minor
                                     , replace = True
                                     , n_samples = train_major.shape[0]
                                     , random_state = 42
                                    )

    train_upsampled = pd.concat([train_major, train_minor_upsampled])
    
    # shuffle the train dataframe to mix up the order to train model
    train = train_upsampled.sample(frac=1)
    
    # features
    features = ['oc'
               , 'hl'
               , '5stdev_adj'
               , '5sma_adj'
              ]
    
    # X_train, X_test, y_train, y_test
    X_train = train[features]
    y_train = train['direction']
    
    X_test = test[features]
    y_test = test['direction']
    
    return X_train, X_test, y_train, y_test, stock_df


def rfc_GridSearch(X_train, y_train, stock_name, days_ahead, cv):
    """
    Inputs: X_train, y_train for GridSearchCV
            days_ahead, int for days head
            cv, int for number of cross validation folds
    Ouptus: <stock_name>.pkl file  
    """
    
    # make grid of hyperparameters
    grid={'bootstrap': [True, False]
           , 'n_estimators': [5, 25, 45, 65, 85, 105]
           , 'max_depth': [1, 2, 3, 4]
           , 'max_features': [1, 2, 3, 4]
           , 'min_samples_leaf': [1, 2, 3, 4]
           , 'min_samples_split': [1, 2, 3]
          }
    
    # gridsearch with 5 fold cross validation
    rfc_gridsearch = GridSearchCV(estimator = RandomForestClassifier()
                                  , param_grid = grid
                                  , cv = cv
                                  , n_jobs = -1
                                 )
    rfc_gridsearch.fit(X_train, y_train)
    
    # save best hyperparameters
    joblib.dump(rfc_gridsearch.best_params_
                , f'./pickles/{stock_name}{days_ahead}.pkl'
                , compress = 1
               )


def rfc(X_train, X_test, y_train, stock_name, days_ahead):
    """
    Inputs: dataframes X_train, X_test, y_train
    Oupts: rfc model, y_pred and y_probs from model
    """
    
    # load best parameters
    rfc = RandomForestClassifier(random_state = 42
                                 , n_jobs = -1
                                ).set_params(**joblib.load(f'./pickles/{stock_name}{days_ahead}.pkl'))
    rfc.fit(X_train, y_train)
    
    return rfc, rfc.predict(X_test), rfc.predict_proba(X_test)[:, 1]
    

    
def roc_plot(y_test, y_probs, stock_name, model_name):
    """
    Inputs: y_test from train test split and y_probs from model.predict_proba()
            stock_name, str of stock name e.g. 'aapl' for apple
            model_name, str of model name e.g. 'Random Forest Classifier'
    Outputs: None, plot of ROC Curve
    """
    
    # figure size 9 by 7
    plt.figure(figsize=(9,7)) 
    
    # ROC Score
    roc_score = roc_auc_score(y_test, y_probs)

    # ROC Curve No Skills Data
    base_fpr, base_tpr, _ = roc_curve(y_test
                                      , [1 for _ in range(len(y_test))]
                                     )

    # ROC Curve Model Data
    model_fpr, model_tpr, _ = roc_curve(y_test
                                        , y_probs
                                       )

    # Plot ROC Curve
    plt.plot(base_fpr
             , base_tpr
             , color = 'b'
             , linestyle = '--'
             , label = 'No Skill'
            )
    
    plt.plot(model_fpr
             , model_tpr
             , color = 'r'
             , label = model_name
            )
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title(f'{stock_name} ROC Curve, Accuracy: {round(roc_score, 3)}')
    plt.legend()
    plt.tight_layout();

    
def prec_recall(y_test, y_probs, stock_name, model_name):
    """
    Inputs: y_test from train test split and y_probs from model.predict_proba()
            stock_name, str of stock name e.g. 'aapl' for apple
            model_name, str of model name e.g. 'Random Forest Classifier'
    Ouputs: None, plot of Precision Recall Curve
    """
    
    # figure size 9 by 7
    plt.figure(figsize=(9,7)) 
    
    # Precision Recall Data
    rfc_prec, rfc_recall, _ = precision_recall_curve(y_test
                                                     , y_probs
                                                    )

    # AUC Score
    auc_score = auc(rfc_recall, rfc_prec)

    # Precision Recall Curve
    plt.plot([0, 0]
                   , linestyle = '--'
                   , color = 'b'
                   , label = 'No Skill'
                  )
    plt.plot(rfc_recall
                   , rfc_prec
                   , color = 'r'
                   , label = model_name
                  )
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title(f'{stock_name} Precision-Recall Curve, Accuracy: {round(auc_score, 3)}')
    plt.legend()
    plt.tight_layout();
    
    
def confusion_matrix(rfc, X_test, y_test, stock_name):
    """
    Inputs: rfc, fitted model from RandomForestClassifier()
            X_test and y_test from train test split
            stock_name, str of stock name e.g. 'aapl' for apple
            model_name, str of model name e.g. 'Random Forest Classifier'
    Outputs: None, plot of Confusion Matrix
    """
    
    plt.rcParams['figure.figsize'] = (9.5, 8.5)
    plt.rcParams['font.size'] = 20
    # Confusion Matrix
    disp = plot_confusion_matrix(rfc, X_test
                                 , y_test
                                 , cmap = plt.cm.Blues
                                 , normalize = 'true'
                                )
    disp.ax_.grid(False)
    disp.ax_.set_title(f'{stock_name} Direction Confusion Matrix')
    plt.tight_layout();
    
    
def cross_validation(rfc, X, y, cv):
    """
    Inputs: rfc, fitted model from RandomForestClassifier()
            X, dataframe with wanted features
            y, pandas series of target or direction of stock
            cv, integer of folds for cross validation
    Outputs: String, average of the cross validation scores
    """
    cvals = cross_val_score(rfc
                       , X
                       , y
                       , scoring = 'accuracy'
                       , cv = cv
                       , n_jobs = -1
                       , verbose = 0
                      )
    return f'{cv} Fold Cross-Validation Score for First RF Model: {np.mean(cvals)}'

































































