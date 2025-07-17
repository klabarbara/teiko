# Bob Loblaw ~~Law Blog~~ Cytometry Trial Dashboard



Dashboard hosted on heroku: https://cytometry-e202f4040d6a.herokuapp.com/
(Note: Patched compare_responders() in analysis.py to aggregate and filter in SQL, as it was dragging. Did so after submission deadline; understood if it doesn't count, but it irked me.)

## Installation and Running

Written using python 3.12.9

### Prereqs: 
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Initialize database/Load Data

load_db is a one-time run script that defines schemas, creates cytometry.db, and imports our csv. Note that load_db.py expects the csv to live in project_root/data/. 

`python load_db.py`

Automation note: Could insert this step into a deployment script or schedule it via whatever CI used/cron. 

### Run Dashboard!

`python dashboard.py`

Once dashboard is running, navigate browser to http://localhost:8050. (should happen programagically, but if not, entering it works fine)

## Database Schema

The schema has two 'partitions'. First, our samples table includes each sample's metadata. Second, the cell metrics for each sample are broken out into a separate cell_counts table. This allows us to scale up and add additional analytics straight into sample or into another, separate table (eg: something something biomarkers?) without having to alter the cell_counts schema. 

I think some of the scale-up strategy depends on what exactly is considered metadata vs. data, and how each of these separate, modular compnonents might scale-up in complexity in turn. This is where subject matter knowledge is helpful. But general strategy is to balance the tension between keeping things as flat as possible (ie: don't make two metadata tables if it can be helped) and keeping things modular for the sake of scaling up and general maintainance, all while establishing a faithfully modeled schema.

One element that I would clarify at standup or similar is the notion of projects. Would scaling up to hundreds of projects change anything schema-wise given the current data? 

## Code Structure/Design

TLDR/BLUF: Data layer, business logic layer, and presentation/UI layer

- db.py: I defined tables with the SQLAlchemy ORM. This is what I know, but it also gives us flexibilty in which specific SQL, in case we have constraints. It's the middle-entity between python and our database. I kept init_db and load_csv within the file, but have the runner load_db as a separate file mostly for convention's sake given the simplicity of the assignment, but it would make more sense if there were multiple scripts accessing db.py (testing scripts, CLI stuff, whatever). 

- analysis.py: This is where our business logic lives. I included the boxplots in here, but left the bar/pie charts in dashboard.py. But looking at it now I would probably unify the chart location in analysis (or a separate file/structure if visualizations became complex enough). Here's an interesting thing: I have code to compute relative frequencies in both analysis and dashboard! Analysis's compute_relative_frequencies is meant to batch load all samples into a df to run our other analysis/statistics (see: responder comparison). Dashboard's is all about taking advantage of pagination for the sake of our compute/UX/sanity. It only fetches ten rows at a time, so the app doesn't chug. Given that, embedding it into our UI logic felt like the cleanest answer as opposed to adding to analysis.py's function, which could make it unwieldy and therefore generate tech debt. 

- dashboard.py: I divided the dashboard into tabs for the initial table, the responder box plots, the significance results, and our baseline subset. I augmented the initial table with the ability to visualize the relative frequencies. It can be hard to appreciate the actual difference between five stacked numbers. I also added a search on sample name, which helps users zero in on specific samples. The dataset is already big enough to justify this, but as it scales up, search (and probably a more robust search) becomes mandatory. The responder analysis and significance tabs might not require a stand alone tab. I drew it up that way mostly to give the other two tabs room to breathe. I would enrich the significance tab with other statistical analyses if the project(s) warranted it. I would also rework analysis.py's significance function accordingly. I think I would merge the boxplots in with the baseline subset tab, but since it was called out in a different 'part' of the assignment, I asssumed it represented a distinct workflow. This could be cleared up with a conversation. Lastly, the baseline subset tab contains our subset analysis. I wanted to demonstrate how I could extend this functionality to other subsets, so included a filter to play around with the different combinations. This extension is representative of what my breadth-scaling strategy would look like in other tabs.

Final notes: I tried to comment/mark where I overtly used AI to help me out. Generally it's to more quickly generate sound UI, to guide statistic selection (always try to make sure its suggestions are grounded), or when debugging hits a wall. Lastly, the comments and readme are a little looser than they would be for a client-facing application in order to highlight my thought process and understanding for hiring purposes. 