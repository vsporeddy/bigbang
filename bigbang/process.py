from bigbang.parse import get_date
import pandas as pd
import datetime
import networkx as nx
import numpy as np
import email.utils
import re

import Levenshtein
from functools import partial


def consolidate_senders_activity(activity_df, to_consolidate):
    """
    takes a DataFrame in the format returned by activity
    takes a list of tuples of format ('from 1', 'from 2') to consolidate
    returns the consolidated DataFrame (a copy, not in place)
    """

    df = activity_df.copy(deep=True)
    for consolidate in to_consolidate:
        column_a, column_b = consolidate
        if column_a in df.columns and column_b in df.columns:
            df[column_a] = df[column_a] + df[column_b]
            df.drop(column_b, inplace=True, axis=1)  # delete the second column
    return df


def matricize(series, func):
    """
    create a matrix by applying func to pairwise combos of elements in a Series
    returns a square matrix as a DataFrame
    should return a symmetric matrix if func(a,b) == func(b,a)
    should return the identity matrix if func == '=='
    """
    matrix = pd.DataFrame(columns=series, index=series)
    for index, element in enumerate(series):
        for second_index, second_element in enumerate(series):
            matrix.iloc[index, second_index] = func(element, second_element)

    return matrix


def minimum_but_not_self(column, dataframe):
    minimum = 100
    for index, value in dataframe[column].iteritems():
        if index == column:
            continue
        if value < minimum:
            minimum = value
    return minimum


def sorted_matrix(from_dataframe,limit=None,sort_key=None):
    if limit is None:
        limit = len(from_dataframe.columns)

    distancedf = matricize(from_dataframe.columns[:limit], from_header_distance)

    # specify that the values in the matrix are integers
    df = distancedf.astype(int)

    if sort_key is not None:
        #sort_for_this_df = partial(minimum_but_not_self, dataframe=df)
        new_columns = sorted(df.columns, key=sort_key)

    new_df = df.reindex(index=new_columns, columns=new_columns)

    return df


def resolve_sender_entities(arx):
    """
    Given an Archive, return a list of lists, each containing
    message senders ('From' fields) that have been groups to be
    probably the same entity.
    """
    act = arx.get_activity()

    # senders orders by descending total activity
    senders = act.sum(0).order(ascending=False)
    senders_act = senders.index

    # senders in lexical order
    senders_lex = act.columns.order()
    senders_lex_dict = dict([(p[1],p[0]) for p in enumerate(senders_lex)])

    n = len(senders)
    # binary matrix of similarity between entries
    sim = np.zeros((n,n))

    # find similarity 
    for i in range(n):
        name = senders_act[i]
        i = senders_lex_dict[name]
    
        # checking only lexically close entries and
        # in proportion to total activity
        # is a performance hack.
        for j in range(i - (n - i + 1) / 2, i + (n - i + 1) / 2):
            d = from_header_distance(senders_lex[i],senders_lex[j])
            sim[i,j] = (d == 0)

    # An entity is a connected component of the resulting graph
    G = nx.Graph(sim)
    entities_list = [[senders_lex[j] for j in x] for x in nx.connected_components(G)]

    # given each entity a label based on its most active 'member'
    entities_dict = {}
    for e in entities_list:
        # TODO: tighten up this labeling function
        label = sorted(e,key=lambda n:senders[n],reverse=True)[0]
        entities_dict[label] = e

    return entities_dict


ren = "([\w\+\.\-]+(\@| at )[\w+\.\-]*) \((.*)\)"
def from_header_distance(a, b):
    """
    A distance measure specifically for the 'From' header of emails.
    Normalizes based on common differences in client handling of email,
    then computes Levenshtein distance between components of the field.
    """
    # this translate table is one way you are supposed to
    # delete characters from a unicode string
    stop_characters = unicode('"<>')
    stop_characters_map = dict((ord(char), None) for char in stop_characters)

    a_normal = unicode(a).lower().translate(stop_characters_map).replace(' at ','@')
    b_normal = unicode(b).lower().translate(stop_characters_map).replace(' at ','@')

    ag = re.match(ren,a_normal)
    bg = re.match(ren,b_normal)
    
    dist = float("inf")

    if ag is None or bg is None:
        print "malformed pair:"
        print ag
        print bg
        dist = Levenshtein.distance(a_normal, b_normal)
    else:
        dist = Levenshtein.distance(ag.groups()[0],bg.groups()[0]) \
               + Levenshtein.distance(ag.groups()[1],bg.groups()[1])

        if len(ag.groups()[2]) > 5 and len(ag.groups()[2]) > 5:
            dist = min(dist,Levenshtein.distance(ag.groups()[2],bg.groups()[2]))

    return dist
