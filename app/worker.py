import logging
import time
from .models import Base, database
from .ingest import process_one
from .services.analysis_jobs import process_analysis


def main():
    logging.basicConfig(level=logging.INFO)
    engine, factory = database()
    Base.metadata.create_all(engine)
    while True:
        try:
            imported=process_one(factory)
            analyzed=process_analysis(factory)
            if not imported and not analyzed:
                time.sleep(1)
        except KeyboardInterrupt:
            return
        except Exception:
            logging.exception('Job transaction rolled back; retrying in 5 seconds')
            time.sleep(5)


if __name__ == '__main__':
    main()
