from collections.abc import Callable
from typing import Any

import pandas as pd

from strategies.bollinger import generate_bollinger_signals
from strategies.donchian import generate_donchian_signals
from strategies.macd import generate_macd_signals
from strategies.momentum import generate_momentum_signals
from strategies.moving_average import generate_moving_average_signals
from strategies.atr_breakout import generate_atr_breakout_signals
from strategies.ema import generate_ema_signals
from strategies.stochastic import generate_stochastic_signals
from strategies.rsi import generate_rsi_signals
from strategies.adx import generate_adx_signals
from strategies.cci import generate_cci_signals
from strategies.keltner import generate_keltner_signals
from strategies.multi_timeframe_trend import generate_multi_timeframe_trend_signals
from strategies.regime_filtered_trend import generate_regime_filtered_trend_signals
from strategies.volatility_targeted_momentum import generate_volatility_targeted_momentum_signals
from typing import Any, TypeAlias

StrategyFunction = Callable[..., pd.DataFrame]
StrategyParameters: TypeAlias = dict[str, Any]


STRATEGIES: dict[str, StrategyFunction] = {
    "moving_average": generate_moving_average_signals,
    "ema": generate_ema_signals,
    "rsi": generate_rsi_signals,
    "bollinger": generate_bollinger_signals,
    "stochastic": generate_stochastic_signals,
    "macd": generate_macd_signals,
    "momentum": generate_momentum_signals,
    "donchian": generate_donchian_signals,
    "atr_breakout": generate_atr_breakout_signals,
    "adx": generate_adx_signals,
    "cci": generate_cci_signals,
    "keltner": generate_keltner_signals,
    "regime_filtered_trend": generate_regime_filtered_trend_signals,
    "multi_timeframe_trend": generate_multi_timeframe_trend_signals,
    "volatility_targeted_momentum": generate_volatility_targeted_momentum_signals,
}


STRATEGY_METADATA: dict[str, dict[str, Any]] = {
    "moving_average": {
        "display_name": "Moving-Average Crossover",
        "family": "Trend Following",
        "subtype": "Moving-Average Trend",
        "features": ["Simple Moving Averages", "Trend Confirmation", "Long/Cash"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Persistent directional trends",
        "favorable_environment": (
            "Sustained directional trends with relatively few reversals and enough "
            "persistence for a lagging moving-average signal to remain invested."
        ),
        "unfavorable_environment": (
            "Sideways or rapidly reversing markets, where repeated crossovers can "
            "create whipsaw and unnecessary turnover."
        ),
        "main_risks": (
            "Signal lag, whipsaw in choppy markets, and sensitivity to the spacing "
            "between the fast and slow windows."
        ),
        "optimization_notes": (
            "Prefer broad regions where several nearby fast/slow combinations perform "
            "similarly. Very short windows can fit noise and increase turnover."
        ),
        "validation_focus": (
            "Check whether selected fast/slow windows remain reasonably stable across "
            "walk-forward folds and whether performance survives trend reversals."
        ),
        "related_strategies": ["EMA Crossover", "MACD Crossover", "ADX Trend Filter"],
        "description": (
            "Holds the asset when its short-term simple moving "
            "average is above its long-term moving average."
        ),
        "thesis": (
            "Persistent price trends may continue after they "
            "have become observable."
        ),
        "parameters": {
            "fast_window": {
                "label": "Fast moving-average window",
                "type": "int",
                "default": 20,
                "min": 2,
                "max": 250,
                "step": 1,
            },
            "slow_window": {
                "label": "Slow moving-average window",
                "type": "int",
                "default": 50,
                "min": 3,
                "max": 500,
                "step": 1,
            },
        },
    },
    "ema": {
        "display_name": "EMA Crossover",
        "family": "Trend Following",
        "subtype": "Moving-Average Trend",
        "features": ["Exponential Moving Averages", "Faster Trend Response", "Long/Cash"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Responsive trend-following conditions",
        "favorable_environment": (
            "Persistent trends in which giving more weight to recent prices helps the "
            "signal react to directional changes without excessive false reversals."
        ),
        "unfavorable_environment": (
            "Noisy range-bound markets, especially when short EMA windows react to "
            "minor price fluctuations that do not develop into trends."
        ),
        "main_risks": (
            "Whipsaw, lag despite faster weighting, and over-sensitivity when the fast "
            "window is made too short relative to the slow window."
        ),
        "optimization_notes": (
            "Look for a stable band of fast/slow pairs rather than one isolated pair. "
            "Aggressive short windows should be checked carefully for turnover costs."
        ),
        "validation_focus": (
            "Observe whether faster optimized windows repeatedly survive unseen periods "
            "or collapse when market noise increases."
        ),
        "related_strategies": ["Moving-Average Crossover", "MACD Crossover", "Keltner Channel Breakout"],
        "description": (
            "Holds the asset when a fast exponential moving "
            "average is above a slower exponential average."
        ),
        "thesis": (
            "Recent price information may identify trend changes "
            "faster than simple moving averages."
        ),
        "parameters": {
            "fast_window": {
                "label": "Fast EMA window",
                "type": "int",
                "default": 12,
                "min": 2,
                "max": 250,
                "step": 1,
            },
            "slow_window": {
                "label": "Slow EMA window",
                "type": "int",
                "default": 26,
                "min": 3,
                "max": 500,
                "step": 1,
            },
        },
    },
    "rsi": {
        "display_name": "RSI Mean Reversion",
        "family": "Mean Reversion",
        "subtype": "Oscillator Mean Reversion",
        "features": ["RSI Oscillator", "Oversold Entry", "Recovery Exit"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Range-bound rebound conditions",
        "favorable_environment": (
            "Range-bound or gently trending markets where sharp short-term selloffs are "
            "often followed by partial rebounds."
        ),
        "unfavorable_environment": (
            "Persistent downtrends, where an asset can remain oversold for an extended "
            "period and repeated rebound assumptions can fail."
        ),
        "main_risks": (
            "Catching a falling market too early, threshold sensitivity, and long holding "
            "periods when momentum does not recover promptly."
        ),
        "optimization_notes": (
            "Thresholds can overfit strongly. Prefer parameter regions where nearby RSI "
            "windows and entry/exit levels give similar outcomes."
        ),
        "validation_focus": (
            "Test whether oversold entries continue to mean-revert out of sample, "
            "especially during prolonged bearish regimes."
        ),
        "related_strategies": ["Stochastic Mean Reversion", "CCI Mean Reversion", "Bollinger-Band Mean Reversion"],
        "description": (
            "Enters after RSI reaches an oversold level and "
            "exits after momentum recovers."
        ),
        "thesis": (
            "Large short-term declines may be followed by "
            "partial price reversals."
        ),
        "parameters": {
            "window": {
                "label": "RSI window",
                "type": "int",
                "default": 14,
                "min": 2,
                "max": 100,
                "step": 1,
            },
            "entry_threshold": {
                "label": "Entry threshold",
                "type": "float",
                "default": 30.0,
                "min": 0.0,
                "max": 99.0,
                "step": 1.0,
            },
            "exit_threshold": {
                "label": "Exit threshold",
                "type": "float",
                "default": 55.0,
                "min": 1.0,
                "max": 100.0,
                "step": 1.0,
            },
        },
    },
    "bollinger": {
        "display_name": "Bollinger-Band Mean Reversion",
        "family": "Mean Reversion",
        "subtype": "Volatility-Band Mean Reversion",
        "features": ["Bollinger Bands", "Volatility-Adjusted Entry", "Mean Reversion"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Oscillating mean-reverting markets",
        "favorable_environment": (
            "Markets that repeatedly oscillate around a relatively stable local mean, "
            "with temporary excursions beyond volatility-adjusted bands."
        ),
        "unfavorable_environment": (
            "Strong directional breakouts, where price can continue moving beyond the "
            "band instead of reverting toward the rolling average."
        ),
        "main_risks": (
            "Mistaking a genuine breakout for a temporary deviation and sensitivity to "
            "both the rolling window and band-width multiplier."
        ),
        "optimization_notes": (
            "Very narrow bands can create excessive entries; very wide bands can create "
            "few observations. Robustness across both window and multiplier matters."
        ),
        "validation_focus": (
            "Check whether band excursions retain mean-reverting behavior in later "
            "periods and whether trade frequency remains sufficient."
        ),
        "related_strategies": ["RSI Mean Reversion", "CCI Mean Reversion", "Keltner Channel Breakout"],
        "description": (
            "Enters below the lower volatility band and exits "
            "when price returns to its rolling average."
        ),
        "thesis": (
            "Price deviations from a volatility-adjusted mean "
            "may eventually reverse."
        ),
        "parameters": {
            "window": {
                "label": "Rolling window",
                "type": "int",
                "default": 20,
                "min": 2,
                "max": 250,
                "step": 1,
            },
            "number_of_std": {
                "label": "Standard-deviation multiplier",
                "type": "float",
                "default": 2.0,
                "min": 0.1,
                "max": 5.0,
                "step": 0.1,
            },
        },
    },
    "stochastic": {
        "display_name": "Stochastic Mean Reversion",
        "family": "Mean Reversion",
        "subtype": "Range-Oscillator Mean Reversion",
        "features": ["Stochastic Oscillator", "Recent Range Position", "Threshold Exit"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Range-bound price oscillations",
        "favorable_environment": (
            "Range-bound markets where moves toward the bottom of a recent trading range "
            "are frequently followed by recoveries toward the upper part of that range."
        ),
        "unfavorable_environment": (
            "Persistent directional trends, because price can remain near one edge of "
            "its recent range for long periods."
        ),
        "main_risks": (
            "Repeated entries against a strong downtrend, threshold overfitting, and "
            "sensitivity to the lookback window."
        ),
        "optimization_notes": (
            "Entry and exit thresholds should not be judged independently. Look for "
            "stable combinations and adequate trade counts rather than extreme settings."
        ),
        "validation_focus": (
            "Inspect whether the chosen thresholds continue to separate temporary range "
            "extremes from persistent trends across walk-forward folds."
        ),
        "related_strategies": ["RSI Mean Reversion", "CCI Mean Reversion", "Bollinger-Band Mean Reversion"],
        "description": (
            "Enters when price is near the bottom of its recent "
            "trading range and exits near the top."
        ),
        "thesis": (
            "Extremely low positions within a recent price range "
            "may be followed by a rebound."
        ),
        "parameters": {
            "window": {
                "label": "Stochastic window",
                "type": "int",
                "default": 14,
                "min": 2,
                "max": 250,
                "step": 1,
            },
            "entry_threshold": {
                "label": "Entry threshold",
                "type": "float",
                "default": 20.0,
                "min": 0.0,
                "max": 99.0,
                "step": 1.0,
            },
            "exit_threshold": {
                "label": "Exit threshold",
                "type": "float",
                "default": 80.0,
                "min": 1.0,
                "max": 100.0,
                "step": 1.0,
            },
        },
    },
    "macd": {
        "display_name": "MACD Crossover",
        "family": "Trend Following",
        "subtype": "Momentum-Trend Crossover",
        "features": ["MACD", "EMA Spread", "Signal-Line Confirmation"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Persistent directional momentum",
        "favorable_environment": (
            "Directional markets where changes in the relationship between faster and "
            "slower exponential trends persist long enough to capture a meaningful move."
        ),
        "unfavorable_environment": (
            "Choppy markets with frequent momentum reversals around the signal line."
        ),
        "main_risks": (
            "High turnover from repeated crossovers, lag around abrupt reversals, and "
            "three-parameter interaction risk."
        ),
        "optimization_notes": (
            "Because fast, slow, and signal windows interact, isolated optima are easy to "
            "produce. Give extra weight to robustness diagnostics and transaction costs."
        ),
        "validation_focus": (
            "Track whether optimized window relationships remain stable and whether high "
            "turnover continues to be justified out of sample."
        ),
        "related_strategies": ["EMA Crossover", "Moving-Average Crossover", "Price Momentum"],
        "description": (
            "Holds the asset when the MACD line is above its "
            "signal line."
        ),
        "thesis": (
            "Recent price momentum may reveal the beginning "
            "or continuation of a trend."
        ),
        "parameters": {
            "fast_window": {
                "label": "Fast EMA window",
                "type": "int",
                "default": 12,
                "min": 2,
                "max": 100,
                "step": 1,
            },
            "slow_window": {
                "label": "Slow EMA window",
                "type": "int",
                "default": 26,
                "min": 3,
                "max": 250,
                "step": 1,
            },
            "signal_window": {
                "label": "Signal-line window",
                "type": "int",
                "default": 9,
                "min": 2,
                "max": 100,
                "step": 1,
            },
        },
    },
    "momentum": {
        "display_name": "Price Momentum",
        "family": "Momentum",
        "subtype": "Time-Series Momentum",
        "features": ["Lookback Return", "Momentum Threshold", "Long/Cash"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Medium-term momentum persistence",
        "favorable_environment": (
            "Assets with persistent medium-term directional movement where positive past "
            "returns tend to be followed by continued strength."
        ),
        "unfavorable_environment": (
            "Frequent sharp reversals or directionless markets where recent winners do "
            "not continue in the same direction."
        ),
        "main_risks": (
            "Momentum crashes after sudden reversals, lookback sensitivity, and delayed "
            "re-entry after rapid recoveries."
        ),
        "optimization_notes": (
            "The lookback horizon often matters more than small threshold changes. Check "
            "whether nearby horizons show a plateau instead of one lucky period length."
        ),
        "validation_focus": (
            "Evaluate whether momentum persistence exists across different regimes rather "
            "than only during one extended bull trend."
        ),
        "related_strategies": ["Volatility-Targeted Momentum", "MACD Crossover", "Daily and Weekly Trend Confirmation"],
        "description": (
            "Holds the asset when its return over a selected "
            "lookback period exceeds a threshold."
        ),
        "thesis": (
            "Assets that recently performed well may continue "
            "performing well in the near future."
        ),
        "parameters": {
            "lookback_window": {
                "label": "Momentum lookback window",
                "type": "int",
                "default": 60,
                "min": 2,
                "max": 500,
                "step": 1,
            },
            "threshold": {
                "label": "Minimum lookback return",
                "type": "float",
                "default": 0.0,
                "min": -1.0,
                "max": 5.0,
                "step": 0.01,
                "format": "percent",
            },
        },
    },
    "donchian": {
        "display_name": "Donchian Breakout",
        "family": "Breakout",
        "subtype": "Price-Channel Breakout",
        "features": ["Rolling High/Low", "Breakout Entry", "Trailing Channel Exit"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Persistent breakout trends",
        "favorable_environment": (
            "Markets that move from consolidation into sustained directional trends, "
            "allowing new highs to lead to continued price expansion."
        ),
        "unfavorable_environment": (
            "Sideways markets with repeated false breakouts and quick reversals back "
            "inside the prior range."
        ),
        "main_risks": (
            "False breakouts, delayed exits after trend reversals, and sensitivity to the "
            "relationship between entry and exit windows."
        ),
        "optimization_notes": (
            "The heatmap is especially informative here. Prefer broad neighboring regions "
            "of good entry/exit pairs over a single narrow maximum."
        ),
        "validation_focus": (
            "Check whether breakout lengths remain consistent across folds and whether a "
            "robust candidate preserves performance better than the raw optimum."
        ),
        "related_strategies": ["ATR Breakout", "Keltner Channel Breakout", "Moving-Average Crossover"],
        "description": (
            "Enters when price exceeds a previous rolling high "
            "and exits after falling below a rolling low."
        ),
        "thesis": (
            "A breakout beyond a recent trading range may "
            "develop into a persistent trend."
        ),
        "parameters": {
            "entry_window": {
                "label": "Entry breakout window",
                "type": "int",
                "default": 50,
                "min": 2,
                "max": 500,
                "step": 1,
            },
            "exit_window": {
                "label": "Exit breakout window",
                "type": "int",
                "default": 20,
                "min": 2,
                "max": 500,
                "step": 1,
            },
        },
    },
    "atr_breakout": {
        "display_name": "ATR Breakout",
        "family": "Breakout",
        "subtype": "Volatility-Adjusted Breakout",
        "features": ["Average True Range", "Trend Level", "Volatility-Scaled Entry"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Volatility-scaled breakout trends",
        "favorable_environment": (
            "Markets where unusually large moves relative to recent volatility tend to "
            "develop into persistent directional trends."
        ),
        "unfavorable_environment": (
            "Highly erratic markets where large ATR-scaled moves frequently reverse "
            "instead of developing into trends."
        ),
        "main_risks": (
            "False volatility breakouts, changing volatility regimes, and interaction "
            "between ATR window, trend window, and multiplier."
        ),
        "optimization_notes": (
            "Multiplier and windows jointly determine selectivity. Avoid interpreting a "
            "high-performing isolated three-parameter combination as stable evidence."
        ),
        "validation_focus": (
            "Check whether the same volatility-adjusted breakout logic survives both calm "
            "and turbulent unseen periods."
        ),
        "related_strategies": ["Donchian Breakout", "Keltner Channel Breakout", "ADX Trend Filter"],
        "description": (
            "Enters after price exceeds a rolling trend level by "
            "a multiple of recent average true range."
        ),
        "thesis": (
            "A price move large relative to recent volatility may "
            "signal the beginning of a meaningful breakout."
        ),
        "parameters": {
            "atr_window": {
                "label": "ATR window",
                "type": "int",
                "default": 14,
                "min": 2,
                "max": 250,
                "step": 1,
            },
            "trend_window": {
                "label": "Trend window",
                "type": "int",
                "default": 20,
                "min": 2,
                "max": 500,
                "step": 1,
            },
            "atr_multiplier": {
                "label": "ATR multiplier",
                "type": "float",
                "default": 1.0,
                "min": 0.1,
                "max": 10.0,
                "step": 0.1,
            },
        },
    },
    "adx": {
        "display_name": "ADX Trend Filter",
        "family": "Trend Following",
        "subtype": "Trend-Strength Filter",
        "features": ["ADX", "Directional Indicators", "Trend Strength", "Moving-Average Filter"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Strong established directional trends",
        "favorable_environment": (
            "Markets with sustained directional trends that become strong enough for ADX "
            "to distinguish them from weak or directionless periods."
        ),
        "unfavorable_environment": (
            "Slow emerging trends that are missed while ADX is still low, or noisy markets "
            "where strength readings rise only after much of the move has occurred."
        ),
        "main_risks": (
            "Late entry, missed low-strength trends, and threshold/window combinations "
            "that fit a particular volatility regime."
        ),
        "optimization_notes": (
            "ADX thresholds can create sharp changes in participation. Prefer settings "
            "whose performance remains stable across adjacent thresholds and windows."
        ),
        "validation_focus": (
            "Observe whether ADX continues to filter weak regimes effectively and whether "
            "the optimized strength threshold remains stable across folds."
        ),
        "related_strategies": ["Moving-Average Crossover", "Volatility-Filtered Trend", "ATR Breakout"],
        "description": (
            "Holds the asset only when price is above its trend average, "
            "ADX confirms sufficient trend strength, and +DI exceeds -DI "
            "to confirm bullish direction."
        ),
        "thesis": (
            "Trend strategies may perform more reliably when weak "
            "or directionless market periods are filtered out."
        ),
        "parameters": {
            "adx_window": {
                "label": "ADX window",
                "type": "int",
                "default": 14,
                "min": 2,
                "max": 100,
                "step": 1,
            },
            "trend_window": {
                "label": "Trend window",
                "type": "int",
                "default": 50,
                "min": 2,
                "max": 500,
                "step": 1,
            },
            "adx_threshold": {
                "label": "Minimum ADX",
                "type": "float",
                "default": 25.0,
                "min": 0.0,
                "max": 100.0,
                "step": 1.0,
            },
        },
    },
    "cci": {
        "display_name": "CCI Mean Reversion",
        "family": "Mean Reversion",
        "subtype": "Deviation-Oscillator Mean Reversion",
        "features": ["CCI", "Typical-Price Deviation", "Threshold Reversal"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Repeated reversals from price extremes",
        "favorable_environment": (
            "Markets where unusually large deviations from a recent typical-price average "
            "are temporary and subsequently reverse."
        ),
        "unfavorable_environment": (
            "Strong persistent trends in which extreme CCI readings reflect genuine "
            "directional movement rather than temporary dislocation."
        ),
        "main_risks": (
            "Entering against persistent trends, threshold sensitivity, and sparse trades "
            "when extreme levels are set too far away."
        ),
        "optimization_notes": (
            "Large threshold ranges make parameter mining easy. Treat extreme optimized "
            "thresholds cautiously unless neighboring values behave similarly."
        ),
        "validation_focus": (
            "Check whether extreme deviations continue to mean-revert out of sample and "
            "whether the strategy remains active enough for conclusions to be meaningful."
        ),
        "related_strategies": ["RSI Mean Reversion", "Stochastic Mean Reversion", "Bollinger-Band Mean Reversion"],
        "description": (
            "Enters after an unusually negative CCI deviation and exits "
            "when CCI reverts toward its neutral level."
        ),
        "thesis": (
            "Extreme negative deviations in typical price may eventually "
            "revert toward their recent average rather than persist."
        ),
        "parameters": {
            "window": {
                "label": "CCI window",
                "type": "int",
                "default": 20,
                "min": 2,
                "max": 250,
                "step": 1,
            },
            "entry_threshold": {
                "label": "Entry threshold",
                "type": "float",
                "default": -100.0,
                "min": -500.0,
                "max": -1.0,
                "step": 10.0,
            },
            "exit_threshold": {
                "label": "Exit threshold",
                "type": "float",
                "default": 0.0,
                "min": -50.0,
                "max": 50.0,
                "step": 10.0,
            },
        },
    },
    "keltner": {
        "display_name": "Keltner Channel Breakout",
        "family": "Breakout",
        "subtype": "Volatility-Channel Breakout",
        "features": ["Keltner Channel", "ATR", "EMA Centerline"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Volatility-adjusted directional breakouts",
        "favorable_environment": (
            "Directional expansions where price breaks beyond an ATR-adjusted channel and "
            "continues trending away from its central EMA."
        ),
        "unfavorable_environment": (
            "Range-bound or noisy periods where price repeatedly crosses the channel "
            "without establishing a persistent trend."
        ),
        "main_risks": (
            "False breakouts, volatility-regime dependence, and three-way interaction "
            "between EMA window, ATR window, and channel width."
        ),
        "optimization_notes": (
            "Channel width controls selectivity while EMA and ATR windows control the "
            "reference level and volatility estimate. Robustness is more important than a single optimum."
        ),
        "validation_focus": (
            "Check whether optimized channel geometry remains effective as volatility "
            "changes and whether trade frequency is stable across folds."
        ),
        "related_strategies": ["ATR Breakout", "Donchian Breakout", "Bollinger-Band Mean Reversion"],
        "description": (
            "Enters when price breaks above an ATR-adjusted "
            "upper channel and exits below the central EMA."
        ),
        "thesis": (
            "A move beyond a volatility-adjusted price channel "
            "may indicate the beginning of a persistent trend."
        ),
        "parameters": {
            "ema_window": {
                "label": "EMA window",
                "type": "int",
                "default": 20,
                "min": 2,
                "max": 250,
                "step": 1,
            },
            "atr_window": {
                "label": "ATR window",
                "type": "int",
                "default": 14,
                "min": 2,
                "max": 250,
                "step": 1,
            },
            "atr_multiplier": {
                "label": "ATR multiplier",
                "type": "float",
                "default": 2.0,
                "min": 0.1,
                "max": 10.0,
                "step": 0.1,
            },
        },
    },
    "regime_filtered_trend": {
        "display_name": "Volatility-Filtered Trend",
        "family": "Trend Following",
        "subtype": "Volatility-Regime Filtered Trend",
        "features": ["Realized Volatility", "Regime Filter", "Trend Average"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Orderly trends in controlled volatility",
        "favorable_environment": (
            "Persistent trends occurring during controlled-volatility regimes, where the "
            "volatility ceiling removes unusually unstable periods."
        ),
        "unfavorable_environment": (
            "Strong trends that happen during high-volatility regimes, because the filter "
            "can remove exposure precisely when large directional moves occur."
        ),
        "main_risks": (
            "Over-filtering, regime misclassification, delayed re-entry, and sensitivity "
            "to the chosen volatility ceiling."
        ),
        "optimization_notes": (
            "The volatility ceiling can act like a regime switch. Inspect sensitivity to "
            "nearby ceilings and avoid relying on one threshold that happens to exclude a bad episode."
        ),
        "validation_focus": (
            "Test whether the volatility ceiling consistently removes harmful regimes "
            "rather than merely excluding one historically bad period."
        ),
        "related_strategies": ["ADX Trend Filter", "Moving-Average Crossover", "Volatility-Targeted Momentum"],
        "features": ["Regime Filter"],
        "description": (
            "Holds the asset when price is above a long-term "
            "trend average and realized volatility remains below "
            "a selected ceiling."
        ),
        "thesis": (
            "Trend-following signals may be more reliable during "
            "controlled-volatility regimes than during unstable "
            "or disorderly markets."
        ),
        "parameters": {
            "trend_window": {
                "label": "Trend window",
                "type": "int",
                "default": 100,
                "min": 2,
                "max": 500,
                "step": 1,
            },
            "volatility_window": {
                "label": "Volatility window",
                "type": "int",
                "default": 20,
                "min": 2,
                "max": 250,
                "step": 1,
            },
            "maximum_volatility": {
                "label": "Maximum annualized volatility",
                "type": "float",
                "default": 0.35,
                "min": 0.01,
                "max": 2.0,
                "step": 0.01,
                "format": "percent",
            },
        },
    },
    "multi_timeframe_trend": {
        "display_name": "Daily and Weekly Trend Confirmation",
        "family": "Trend Following",
        "subtype": "Multi-Timeframe Trend Confirmation",
        "features": ["Multi-Timeframe", "Daily Trend", "Weekly Trend"],
        "signal_style": "Binary long-or-cash exposure",
        "best_suited_for": "Trends confirmed across timeframes",
        "favorable_environment": (
            "Broad directional trends that are visible on both shorter and higher "
            "timeframes, reducing disagreement between local and larger-scale direction."
        ),
        "unfavorable_environment": (
            "Fast reversals or transitional periods where daily and weekly signals remain "
            "out of sync for extended periods."
        ),
        "main_risks": (
            "Late confirmation, reduced market participation, and dependence on how the "
            "two trend horizons interact."
        ),
        "optimization_notes": (
            "Daily and weekly windows should be interpreted jointly. Favor broad combinations "
            "that maintain sensible separation between the two horizons."
        ),
        "validation_focus": (
            "Check whether agreement between timeframes remains useful across regimes and "
            "whether optimized windows repeatedly select similar horizons."
        ),
        "related_strategies": ["Moving-Average Crossover", "EMA Crossover", "ADX Trend Filter"],
        "features": ["Multi-Timeframe"],
        "description": (
            "Holds the asset only when both daily and weekly "
            "trend conditions are positive."
        ),
        "thesis": (
            "Trend signals may be more robust when short-term "
            "and higher-timeframe market direction agree."
        ),
        "parameters": {
            "daily_window": {
                "label": "Daily trend window",
                "type": "int",
                "default": 50,
                "min": 2,
                "max": 500,
                "step": 1,
            },
            "weekly_window": {
                "label": "Weekly trend window",
                "type": "int",
                "default": 20,
                "min": 2,
                "max": 104,
                "step": 1,
            },
        },
    },
    "volatility_targeted_momentum": {
        "display_name": "Volatility-Targeted Momentum",
        "family": "Momentum",
        "subtype": "Risk-Managed Momentum",
        "features": ["Momentum", "Volatility Targeting", "Continuous Position Sizing"],
        "signal_style": "Continuous long-or-cash exposure with volatility-scaled position sizing",
        "best_suited_for": "Momentum with changing market volatility",
        "favorable_environment": (
            "Markets with persistent positive momentum where realized volatility varies "
            "enough for dynamic position sizing to reduce risk during unstable periods."
        ),
        "unfavorable_environment": (
            "Very rapid reversals, volatility spikes followed by immediate recoveries, or "
            "regimes where reducing exposure after volatility rises causes the strategy to miss rebounds."
        ),
        "main_risks": (
            "Volatility estimation lag, frequent small rebalancing changes, path dependence, "
            "and overfitting across several interacting parameters."
        ),
        "optimization_notes": (
            "This has the largest parameter interaction problem in the current library. "
            "Use sensitivity profiles, robustness diagnostics, and walk-forward validation rather than the raw optimum alone."
        ),
        "validation_focus": (
            "Track both objective performance and exposure behavior out of sample. Stable "
            "risk targeting matters as much as selecting the highest in-sample Sharpe ratio."
        ),
        "related_strategies": ["Price Momentum", "Volatility-Filtered Trend", "ADX Trend Filter"],
        "features": ["Risk-Managed Position Sizing"],
        "description": (
            "Uses momentum to determine whether to invest and "
            "realized volatility to determine position size."
        ),
        "thesis": (
            "Momentum exposure may produce a more stable risk "
            "profile when position size decreases during highly "
            "volatile periods."
        ),
        "parameters": {
            "momentum_window": {
                "label": "Momentum window",
                "type": "int",
                "default": 60,
                "min": 2,
                "max": 500,
                "step": 1,
            },
            "volatility_window": {
                "label": "Volatility window",
                "type": "int",
                "default": 20,
                "min": 2,
                "max": 250,
                "step": 1,
            },
            "target_volatility": {
                "label": "Target annualized volatility",
                "type": "float",
                "default": 0.15,
                "min": 0.01,
                "max": 1.0,
                "step": 0.01,
                "format": "percent",
            },
            "maximum_exposure": {
                "label": "Maximum exposure",
                "type": "float",
                "default": 1.0,
                "min": 0.1,
                "max": 2.0,
                "step": 0.1,
            },
            "momentum_threshold": {
                "label": "Minimum momentum return",
                "type": "float",
                "default": 0.0,
                "min": -1.0,
                "max": 5.0,
                "step": 0.01,
                "format": "percent",
            },
        },
    },
}



OPTIMIZATION_GRIDS: dict[str, dict[str, list[Any]]] = {
    "moving_average": {
        "fast_window": [5, 10, 15, 20, 30, 40, 50, 60],
        "slow_window": [30, 50, 75, 100, 125, 150, 200, 250],
    },
    "ema": {
        "fast_window": [5, 8, 12, 16, 20, 26, 30, 40],
        "slow_window": [20, 26, 35, 50, 75, 100, 150, 200],
    },
    "rsi": {
        "window": [7, 10, 14, 18, 21, 28],
        "entry_threshold": [20.0, 25.0, 30.0, 35.0, 40.0],
        "exit_threshold": [45.0, 50.0, 55.0, 60.0, 65.0, 70.0],
    },
    "bollinger": {
        "window": [10, 15, 20, 25, 30, 40, 50, 60],
        "number_of_std": [1.0, 1.5, 2.0, 2.5, 3.0],
    },
    "stochastic": {
        "window": [7, 10, 14, 18, 21, 28],
        "entry_threshold": [10.0, 15.0, 20.0, 25.0, 30.0],
        "exit_threshold": [70.0, 75.0, 80.0, 85.0, 90.0],
    },
    "macd": {
        "fast_window": [5, 8, 12, 16, 20, 26],
        "slow_window": [20, 26, 35, 50, 75, 100],
        "signal_window": [5, 7, 9, 12, 15],
    },
    "momentum": {
        "lookback_window": [10, 20, 40, 60, 90, 120, 180, 252],
        "threshold": [-0.10, -0.05, 0.0, 0.05, 0.10],
    },
    "donchian": {
        "entry_window": [20, 30, 40, 50, 60, 75, 100, 125, 150, 200],
        "exit_window": [5, 10, 15, 20, 25, 30, 40, 50, 75, 100],
    },
    "atr_breakout": {
        "atr_window": [7, 10, 14, 20, 30],
        "trend_window": [10, 20, 30, 50, 75, 100, 150],
        "atr_multiplier": [0.5, 0.75, 1.0, 1.5, 2.0],
    },
    "adx": {
        "adx_window": [7, 10, 14, 20, 30],
        "trend_window": [20, 30, 50, 75, 100, 150, 200],
        "adx_threshold": [15.0, 20.0, 25.0, 30.0, 35.0],
    },
    "cci": {
        "window": [10, 14, 20, 30, 40, 50],
        "entry_threshold": [-200.0, -150.0, -100.0, -75.0, -50.0],
        "exit_threshold": [-25.0, 0.0, 25.0, 50.0],
    },
    "keltner": {
        "ema_window": [10, 15, 20, 30, 50, 75, 100],
        "atr_window": [7, 10, 14, 20, 30],
        "atr_multiplier": [1.0, 1.5, 2.0, 2.5, 3.0],
    },
    "regime_filtered_trend": {
        "trend_window": [30, 50, 75, 100, 125, 150, 200],
        "volatility_window": [10, 15, 20, 30, 40],
        "maximum_volatility": [0.20, 0.25, 0.30, 0.35, 0.40, 0.50],
    },
    "multi_timeframe_trend": {
        "daily_window": [20, 30, 50, 75, 100, 125, 150, 200],
        "weekly_window": [8, 10, 15, 20, 26, 30, 40],
    },
    "volatility_targeted_momentum": {
        "momentum_window": [20, 40, 60, 120, 252],
        "volatility_window": [10, 20, 30, 40],
        "target_volatility": [0.10, 0.15, 0.20],
        "maximum_exposure": [0.75, 1.0, 1.5],
        "momentum_threshold": [-0.05, 0.0, 0.05],
    },
}


def get_optimization_grid(
    strategy_name: str,
) -> dict[str, list[Any]]:
    """
    Return a defensive copy of the default optimization grid.

    These grids are moderately dense research defaults. They are intended to
    identify broad parameter regions without turning the default workflow into
    exhaustive parameter mining.
    """
    if strategy_name not in OPTIMIZATION_GRIDS:
        raise ValueError(
            f"No optimization grid exists for strategy "
            f"'{strategy_name}'."
        )

    return {
        parameter_name: list(values)
        for parameter_name, values
        in OPTIMIZATION_GRIDS[strategy_name].items()
    }
def apply_strategy(
    data: pd.DataFrame,
    strategy_name: str,
    strategy_parameters: StrategyParameters | None = None,
) -> pd.DataFrame:
    """
    Apply a registered strategy to market data.
    """
    if strategy_name not in STRATEGIES:
        available = ", ".join(sorted(STRATEGIES))

        raise ValueError(
            f"Unknown strategy '{strategy_name}'. "
            f"Available strategies: {available}."
        )

    raw_parameters = (
        strategy_parameters
        if strategy_parameters is not None
        else get_default_parameters(strategy_name)
    )

    parameters: dict[str, Any] = {
        str(key): value
        for key, value in raw_parameters.items()
    }

    strategy_function = STRATEGIES[strategy_name]

    return strategy_function(
        data=data,
        **parameters,
    )


def get_default_parameters(
    strategy_name: str,
) -> StrategyParameters:
    """
    Return a strategy's default parameter values.
    """
    if strategy_name not in STRATEGY_METADATA:
        raise ValueError(
            f"No metadata exists for strategy '{strategy_name}'."
        )

    parameter_specs = STRATEGY_METADATA[
        strategy_name
    ]["parameters"]

    return {
        parameter_name: specification["default"]
        for parameter_name, specification
        in parameter_specs.items()
    }