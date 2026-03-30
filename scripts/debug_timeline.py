from data.aggregators.timeline_aggregator import TimelineAggregator
import logging
import json

logging.basicConfig(level=logging.INFO)
agg = TimelineAggregator()
timeline = agg.get_player_timeline("125040")
print(f"Timeline size for Bleda: {len(timeline)}")
if timeline:
    print(f"First milestone: {timeline[0]['type']} - {timeline[0]['label']}")
    # print(json.dumps(timeline[0], indent=2, default=str))
else:
    print("Timeline is empty!")
